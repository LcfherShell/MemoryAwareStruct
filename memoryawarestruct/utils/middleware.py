import os, sys, re, inspect, weakref
from functools import wraps

def replace_special_chars(input_string):
    if not isinstance(input_string, str):
        raise TypeError("Input must be a string.")

    # Remove extra spaces and replace with underscore
    input_string = "_".join(input_string.strip().split())

    if not input_string:
        raise ValueError("Input string is empty after trimming and space replacement.")

    # Separate digits at the beginning
    match = re.match(r"^(\d+)([a-zA-Z_].*)?", input_string)
    if match:
        digits = match.group(1)
        rest = match.group(2) or ""
        input_string = rest + "_" + digits

    # If result is only digits, it's invalid
    if input_string.isdigit():
        raise ValueError(
            "Resulting string contains only digits, which is not a valid name."
        )

    # Replace all non-alphanumeric and non-underscore characters with "_"
    output_string = re.sub(r"[^a-zA-Z0-9_]", "_", input_string)

    if output_string.replace("_", "").__len__() <= 0:
        raise ValueError("Input string is empty after trimming and space replacement.")

    # Strip leading/trailing underscores
    return output_string.strip("_")


def is_all_list(data):
    return all(isinstance(i, list) for i in data)


def clean_json(raw_data: dict):
    # Bersihkan key-key menggunakan fungsi
    cleaned_data = {}
    for key, value in raw_data.items():
        try:
            cleaned_key = replace_special_chars(key)
            cleaned_data[cleaned_key] = value
        except ValueError as e:
            pass
        except TypeError as e:
            pass
    return cleaned_data


def smart_list_to_dict(data):
    """
    Smartly convert mixed list to dict.
    Can detect patterns such as:
      - ["key", value]
      - [{"key": value}]
      - ["key", value, {"key2": val2}]
      - [{"key": [ {"nested": val}, ... ] }, value]
    
    Rules:
    - Only process string keys that are valid (no dots, no starting with digits)
    - Keep flat lists as-is if they don't contain nested structures
    - For key-value pairs, only process if conditions are met
    """
    if not isinstance(data, list) or not data:
        return {}
        
    result = {}
    i = 0
    length = len(data)

    def is_valid_key(item):
        """Validate if item can be a dictionary key"""
        if not isinstance(item, str):
            return False
        if not item.strip():  # Empty string
            return False
        if item[0].isdigit():  # Starts with digit
            return False
        if '.' in item:  # Contains dot
            return False
        return True

    def add_to_result(key, value):
        """Helper to handle duplicate keys"""
        clean_key = replace_special_chars(str(key))
        if clean_key in result:
            if not isinstance(result[clean_key], list):
                result[clean_key] = [result[clean_key]]
            result[clean_key].append(value)
        else:
            result[clean_key] = value

    while i < length:
        item = data[i]

        if isinstance(item, dict):
            # Kasus dict langsung, gabungkan key-nya
            for k, v in item.items():
                if is_valid_key(str(k)):  # Validate dict keys too
                    add_to_result(k, v)
            i += 1

        elif isinstance(item, list):
            # Check if list contains nested structures (dict or list)
            has_nested = any(isinstance(x, (dict, list)) for x in item)
            
            if has_nested:
                # Process nested structures recursively
                sub_dict = smart_list_to_dict(item)
                if sub_dict:  # Only update if conversion was successful
                    result.update(sub_dict)
            else:
                # Flat list - check if it's part of key-value pattern
                if i > 0 and is_valid_key(str(data[i-1])):
                    # Previous item might be a key for this list
                    pass  # Will be handled by key-value logic
                else:
                    # Standalone flat list - keep as is with generated key
                    add_to_result(f"list_{i}", item)
            i += 1

        elif is_valid_key(item) and (i + 1 < length):
            # Valid key pattern - check next item
            key = item
            next_item = data[i + 1]
            
            # Always treat valid string key + next item as key-value pair
            add_to_result(key, next_item)
            i += 2

        else:
            # Invalid key or no pair - skip
            i += 1

    return result


class ProtectedDict(dict):
    """Protected dictionary that prevents external modification"""

    def __init__(self, owner_instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = weakref.ref(owner_instance)
        self._locked = True  # Default to unlocked
        self._authorized_methods = set()
        self._access_count = {}  # Track access count per method
        self._max_access_per_method = 1  # Maximum access allowed per method

    def __dir__(self):
        return []

    def _check_authorization(self):
        """Check if caller is authorized to modify this dict"""

        frame = inspect.currentframe()
        try:
            # Go up the call stack to find the caller
            caller_frame = frame.f_back.f_back if frame.f_back else None
            if not caller_frame:
                return False

            caller_locals = caller_frame.f_locals
            method_name = caller_frame.f_code.co_name

            # Check if caller is the owner instance
            owner = self._owner()
            if owner and "self" in caller_locals:
                if caller_locals["self"] is owner:
                    # Check if method is authorized
                    if method_name in self._authorized_methods:
                        # Check access count limit
                        current_count = self._access_count.get(method_name, 0)
                        if current_count < self._max_access_per_method:
                            self._access_count[method_name] = current_count + 1
                            return True
                        else:
                            return False
                    return False

            return False
        except Exception:
            return False
        finally:
            del frame

    def authorize_method(self, method_name: str, max_access: int = 1):
        """Authorize a method to modify this dict with access limit"""
        self._authorized_methods.add(method_name)
        self._max_access_per_method = max_access

    def reset_access_count(self):
        """Reset access count for all methods"""
        self._access_count.clear()

    def lock(self):
        """Lock the dictionary to prevent modifications"""
        self._locked = True

    def unlock(self):
        """Unlock the dictionary (NOT RECOMMENDED)"""
        self._locked = False

    def __setitem__(self, key, value):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot modify protected dictionary from external context"
            )
        # super().__setitem__(key, value)

    def __delitem__(self, key):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot delete from protected dictionary from external context"
            )
        # super().__delitem__(key)

    def clear(self):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot clear protected dictionary from external context"
            )
        super().clear()

    def pop(self, *args, **kwargs):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot pop from protected dictionary from external context"
            )
        return super().pop(*args, **kwargs)

    def popitem(self):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot popitem from protected dictionary from external context"
            )
        return super().popitem()

    def update(self, *args, **kwargs):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot update protected dictionary from external context"
            )
        super().update(*args, **kwargs)

    def setdefault(self, key, default=None):
        if self._locked or not self._check_authorization():
            raise AttributeError(
                "Dictionary access denied: Cannot setdefault on protected dictionary from external context"
            )
        return super().setdefault(key, default)


class ReadOnlyDictView:
    """Read-only view of dictionary that prevents all modifications"""

    def __init__(self, source_dict):
        self._source = source_dict

    def __dir__(self):
        return []

    def __getitem__(self, key):
        return self._source[key]

    def __iter__(self):
        return iter(self._source)

    def __len__(self):
        return len(self._source)

    def __contains__(self, key):
        return key in self._source

    def get(self, key, default=None):
        return self._source.get(key, default)

    def keys(self):
        return self._source.keys()

    def values(self):
        return self._source.values()

    def items(self):
        return self._source.items()

    def __setitem__(self, key, value):
        raise AttributeError(
            "Dictionary access denied: Cannot modify dictionary through __dict__ access"
        )

    def __delitem__(self, key):
        raise AttributeError(
            "Dictionary access denied: Cannot delete from dictionary through __dict__ access"
        )

    def __repr__(self):
        return f"ReadOnlyDictView({dict(self._source)})"
    
class ProtectedAttribute:
    """Descriptor to protect critical attributes"""

    def __init__(self, initial_value, read_only=False, validator=None):
        self.initial_value = initial_value
        self.read_only = read_only
        self.validator = validator
        self.name = None

    def __dir__(self):
        return []

    def __set_name__(self, owner, name):
        self.name = f"_{name}_protected"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.name, self.initial_value)

    def __set__(self, obj, value):
        if self.read_only and hasattr(obj, self.name):
            raise AttributeError(f"Cannot modify read-only attribute")

        if self.validator and not self.validator(value):
            raise ValueError(f"Invalid value for protected attribute")

        setattr(obj, self.name, value)


def metaClass():
    def protect_method(func):
        """Decorator to protect method from replacement"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Mark as protected
        wrapper._is_protected = True
        wrapper._original_func = func
        return wrapper
    
    class SecureStructMeta(type):
        """Metaclass to secure Struct class"""
        def __init__(cls, name, bases, namespace, **kwargs):
            for base in bases:
                if isinstance(base, SecureStructMeta):
                    raise TypeError(f"Cannot subclass final class '{base.__name__}'")
                
        def __new__(mcs, name, bases, namespace, **kwargs):
            # Daftar method dan atribut yang dilindungi
            protected_items = {
                "__init__",
                "__setattr__",
                "__getattribute__",
                "__delattr__",
                "__dict__",
                "__getitem__",
                "__setitem__",
                "__delitem__",
                "_config",
                "_config_id",
                "_original_entries",
                "_backup_dict",
                "get_struct_name",
                "set_struct_name",
                "restore_backup",
                "reset_to_original",
                "safe_get",
                "safe_set",
                "_protected_attrs",
                "_protected_dict",
                "lock_dict",
                "unlock_dict",
                "_is_internal_call",
            }

            # Tandai method yang dilindungi
            for key, value in namespace.items():
                if key in protected_items and callable(value):
                    namespace[key] = protect_method(value)

            cls = super().__new__(mcs, name, bases, namespace)
            cls._protected_items = protected_items
            return cls
    return SecureStructMeta
    