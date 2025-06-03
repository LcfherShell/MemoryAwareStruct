import os, re, abc, copy, inspect
import difflib
from threading import Lock
import sys, json
import logging
try:
    from memoryawarestruct.utils.typedata import TypeVar, Generic, Any, Union, Optional, Set, OrderedDict
    from memoryawarestruct.utils.middleware import ProtectedDict, ReadOnlyDictView, metaClass, replace_special_chars, smart_list_to_dict
except:
    from utils.typedata import TypeVar, Generic, Any, Union, Optional, Set, OrderedDict
    from utils.middleware import ProtectedDict, ReadOnlyDictView, metaClass, replace_special_chars, smart_list_to_dict


__all__ = ["memory", "create_secure_memory", "SecureMemoryContext"]

# Membuat konfigurasi logger yang lebih canggih tanpa FileHandler
def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set level logging ke DEBUG

    # Membuat format log
    formatter = logging.Formatter('%(levelname)s - %(message)s')

    # Handler untuk menampilkan log ke konsol
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.CRITICAL)  # Menonaktifkan semua log, hanya menunjukkan CRITICAL
    console_handler.setFormatter(formatter)

    # Menambahkan handler ke logger
    logger.addHandler(console_handler)

    return logger

logger = setup_logger('MemoryAwareStruct')
def __main():
    
    SecureStructMeta = metaClass()
    class SelectType:
        Union_ = Union[int, str, float, list, tuple, dict, bool, bytes]
        Any_ = Any
        Dict_ = dict
        List_ = Union[list, tuple]
        Ordered_ = OrderedDict()


    class StructConfig:
        """Configuration class untuk menghindari bentrok global variable"""

        _instances = {}
        _lock = Lock()

        def __init__(self, instance_id: str = "default"):
            self.instance_id = instance_id
            self._name = "MemoryAwareStruct"
            self._defaults = {
                "name": "MemoryAwareStruct",
                "case_sensitive": True,
                "allow_override": True,
            }
            self._locked = False

        def __dir__(self):
            return []

        @classmethod
        def get_instance(cls, instance_id: str = "default"):
            """Get or create config instance"""
            with cls._lock:
                if instance_id not in cls._instances:
                    cls._instances[instance_id] = cls(instance_id)
                return cls._instances[instance_id]

        def set_name(self, name: str):
            """Set memoryawarestruct name for this instance"""
            if not self._locked:
                self._name = name
            else:
                raise RuntimeError("Configuration is locked")

        def get_name(self):
            """Get memoryawarestruct name for this instance"""
            return self._name

        def lock(self):
            """Lock configuration to prevent changes"""
            self._locked = True

        def unlock(self):
            """Unlock configuration"""
            self._locked = False

        def reset_to_defaults(self):
            """Reset configuration to defaults"""
            if not self._locked:
                self._name = self._defaults["name"]

    class ImmutableList(tuple):
        def __new__(cls, iterable):
            # Konversi elemen list ke bentuk yang sudah diamankan
            return super().__new__(cls, [deep_struct_freeze(item) for item in iterable])

        def __init__(self, iterable):
            pass  # Tidak ada init

        def __setitem__(self, *args):
            raise TypeError("ImmutableList does not support item assignment")

        def append(self, *args):
            raise TypeError("ImmutableList does not support append")

        def extend(self, *args):
            raise TypeError("ImmutableList does not support extend")

        def pop(self, *args):
            raise TypeError("ImmutableList does not support pop")

        def remove(self, *args):
            raise TypeError("ImmutableList does not support remove")

        def insert(self, *args):
            raise TypeError("ImmutableList does not support insert")


    class ImmutableDict:
        def __init__(self, data):
            self._data = {k: deep_struct_freeze(v) for k, v in data.items()}

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

        def __contains__(self, key):
            return key in self._data

        def items(self):
            return self._data.items()

        def keys(self):
            return self._data.keys()

        def values(self):
            return self._data.values()

        def __setitem__(self, *args):
            raise TypeError("ImmutableDict does not support item assignment")

        def __delitem__(self, *args):
            raise TypeError("ImmutableDict does not support deletion")

        def __repr__(self):
            return f"ImmutableDict({self._data})"

    def deep_struct_freeze(obj, blacklist: list = None, config_id="default", existing_keys=None):
            if blacklist is None:
                blacklist = ['get_struct_name', 'set_struct_name', 'restore_backup', 'reset_to_original', 'safe_get', 'safe_set', 'dell_dict', 'lock_dict', 'unlock_dict', 'get_dict_protection_status']

            if existing_keys is None:
                existing_keys = set()

            def generate_unique_key(base, used):
                counter = 1
                new_key = base
                while new_key in used:
                    new_key = f"{base}{counter}"
                    counter += 1
                used.add(new_key)
                return new_key

            if isinstance(obj, memoryawarestruct):
                return obj

            if isinstance(obj, dict):
                frozen_items = {}
                used_keys = set(existing_keys)

                for k, v in obj.items():
                    original_key = replace_special_chars(str(k))
                    
                    # Deteksi key mirip blacklist
                    similar = difflib.get_close_matches(original_key, blacklist, n=1, cutoff=0.8)
                    if similar:
                        original_key = generate_unique_key(original_key, used_keys)
                    elif original_key in used_keys:
                        original_key = generate_unique_key(original_key, used_keys)
                    else:
                        used_keys.add(original_key)
                    
                    # Tangani nilai rekursif
                    if isinstance(v, dict):
                        frozen_items[original_key] = memoryawarestruct(
                            original_key,
                            **{
                                replace_special_chars(str(subk)): deep_struct_freeze(
                                    subv, blacklist=blacklist, config_id=original_key
                                )
                                for subk, subv in v.items()
                            },
                        )
                    else:
                        frozen_items[original_key] = deep_struct_freeze(v, blacklist=blacklist, config_id=original_key)
                return memoryawarestruct(config_id, **frozen_items)

            elif isinstance(obj, list):
                return ImmutableList(obj)

            elif isinstance(obj, tuple):
                return ImmutableList(obj)

            elif isinstance(obj, set):
                return frozenset(deep_struct_freeze(i, blacklist=blacklist, config_id=config_id) for i in obj)

            return obj


    class memoryawarestruct(metaclass=SecureStructMeta):
        """
        memoryawarestruct is a highly secure and extensible memory-aware data structure designed to prevent 
        unauthorized access or modification of internal state. It enables controlled dynamic attribute 
        storage while enforcing protection on both attributes and internal dictionaries.

        This class is suitable for secure runtime environments or sensitive data models that 
        require robust encapsulation and anti-tampering mechanisms.

        Features:
            - Dynamic attribute storage and protection
            - Configurable dictionary and attribute protection
            - Safe interface for reading, writing, and deleting keys
            - Method and attribute registry with access control
            - Built-in backup and restoration mechanism

        Parameters:
            __config_id (str): Configuration identifier used to load predefined security config. Default is 'default'.
            __allow_unsafe_operations (bool): If True, allows unsafe modifications. Use with caution.
            __dict_protection (bool): Enables or disables internal dictionary access protection.
            __attr_protection (bool): Enables or disables protection of internal attributes.
            **entries: Initial user-defined attributes to set on the memoryawarestruct.
        """
        def __init__(
            self,
            __config_id: str = "default",
            __allow_unsafe_operations: bool = False,
            __dict_protection: bool = True,
            __attr_protection: bool = True,
            **entries: SelectType.Union_,
        ) -> None:
            """
            Initialize the secure memory with optional configuration and initial attributes.

            Internal states such as protection flags, method registries, and original entries
            are set up during this phase. If dictionary protection is enabled, a `ProtectedDict`
            is used to secure all user-defined attributes.

            Args:
                __config_id (str): The identifier used to retrieve a shared config instance.
                __allow_unsafe_operations (bool): Allows direct changes if set to True. Default is False.
                __dict_protection (bool): Enables protection on the internal dictionary. Default is True.
                __attr_protection (bool): Enables protection on internal attributes. Default is True.
                **entries (dict): Initial key-value pairs to be added to the memoryawarestruct as dynamic attributes.
            """
            # Initialize basic attributes first to avoid AttributeError
            object.__setattr__(self, "_method_registry", {})
            object.__setattr__(self, "_allow_unsafe_operations", __allow_unsafe_operations)
            object.__setattr__(self, "_dict_protection_enabled", __dict_protection)
            object.__setattr__(self, "_attr_protection_enabled", __attr_protection)
            object.__setattr__(self, "_user_attributes", set())
            object.__setattr__(
                self, "_dict_access_blocked", True
            )  # Block all dict access by default

            # Protected attributes - tidak bisa diubah dari luar
            object.__setattr__(self, "_config_id", __config_id)
            object.__setattr__(self, "_config", StructConfig.get_instance(__config_id))
            object.__setattr__(self, "_original_entries", copy.deepcopy(entries))
            object.__setattr__(
                self,
                "_protected_attrs",
                {
                    "_config_id",
                    "_config",
                    "_original_entries",
                    "_backup_dict",
                    "_protected_attrs",
                    "_allow_unsafe_operations",
                    "_method_registry",
                    "_protected_dict",
                    "_dict_protection_enabled",
                    "_attr_protection_enabled",
                    "_user_attributes",
                    "_dict_access_blocked",
                },
            )

            # Register original methods
            self._register_original_methods()

            # Buat protected dictionary sebagai pengganti __dict__
            if __dict_protection:
                object.__setattr__(self, "_protected_dict", ProtectedDict(self))
                # Authorize ONLY internal methods to modify the dict - VERY LIMITED
                self._protected_dict.authorize_method(
                    "_internal_dict_update", max_access=1000
                )  # Allow multiple internal updates
            else:
                object.__setattr__(self, "_protected_dict", None)
            if entries.__len__() >= 1:
                entries = smart_list_to_dict([entries])

            # Update dengan entries yang diberikan
            for key, value in entries.items():
                key = replace_special_chars(key)
                if not key.startswith("_"):
                    self._internal_dict_update(key, value)
                    self._user_attributes.add(key)

        def __dir__(self):
            return [
                "config",
                "lock_dict",
                "get_dict_protection_status",
                "set_struct_name",
                "insert_dict",
                "update_dict",
                "dell_dict",
                "restore_backup",
                "reset_to_original",
                "safe_set",
                "safe_get",
                "get_protection_status",
                "__repr__",
                "__str__",
            ]

        def _is_internal_call(self) -> bool:
            """Check if the call is coming from internal methods"""
            frame = inspect.currentframe()
            try:
                # Check multiple frames up the call stack
                current_frame = frame.f_back
                internal_call_found = False

                while current_frame and not internal_call_found:
                    caller_locals = current_frame.f_locals
                    method_name = current_frame.f_code.co_name

                    # List of internal methods allowed to modify attributes
                    internal_methods = {
                        "__init__",
                        "_internal_dict_update",
                        "safe_set",
                        "restore_backup",
                        "reset_to_original",
                        "update_dict",
                        "insert_dict",
                        "dell_dict",
                    }

                    # If we find an internal method in the call stack
                    if method_name in internal_methods and "self" in caller_locals:
                        if caller_locals["self"] is self:
                            internal_call_found = True
                            break

                    current_frame = current_frame.f_back

                return internal_call_found
            except Exception:
                return False
            finally:
                del frame

        def _internal_dict_update(self, key: str, value: Any):
            """Internal method to update dictionary safely with reserved name protection"""

            # Define method blacklist
            protected_names = set([ name for name, obj in inspect.getmembers(self, inspect.ismethod)])

            # Sanitize key
            original_key = replace_special_chars(str(key))

            # Periksa kemiripan dengan blacklist
            similar = difflib.get_close_matches(original_key, protected_names, n=1, cutoff=0.9)

            # Jika mirip, atau key sudah ada, modifikasi nama
            def generate_unique_key(base_key, existing_keys):
                counter = 1
                new_key = base_key
                while new_key in existing_keys or new_key in protected_names:
                    new_key = f"{base_key}{counter}"
                    counter += 1
                return new_key

            existing_keys = set(self.get_user_attributes().keys()) if hasattr(self, "get_user_attributes") else set()
            if similar or original_key in existing_keys or original_key in protected_names:
                original_key = generate_unique_key(original_key, existing_keys)

            # Bekukan nilainya
            frozen_value = deep_struct_freeze(value, blacklist=list(protected_names), config_id=self._config_id)

            # Set sebagai atribut
            object.__setattr__(self, original_key, frozen_value)

            if self._protected_dict is not None:
                was_locked = self._protected_dict._locked
                self._protected_dict._locked = False
                try:
                    self._protected_dict[original_key] = frozen_value
                finally:
                    self._protected_dict._locked = was_locked

            if not original_key.startswith("_"):
                self._user_attributes.add(original_key)


        def _register_original_methods(self):
            """Register original methods are used for protection"""
            methods_to_protect = [
                "get_struct_name",
                "set_struct_name",
                "restore_backup",
                "reset_to_original",
                "safe_get",
                "safe_set",
                "dell_dict",
                "lock_dict",
                "unlock_dict",
                "get_dict_protection_status",
            ]

            for method_name in methods_to_protect:
                if hasattr(self, method_name):
                    original_method = getattr(self, method_name)
                    self._method_registry[method_name] = original_method

        def __setattr__(self, name: str, value: Any) -> None:
            # IZINKAN jika ini adalah property dengan setter
            cls_attr = getattr(type(self), name, None)
            if isinstance(cls_attr, property) and cls_attr.fset:
                return cls_attr.fset(self, value)
            if hasattr(self, "_protected_attrs") and name in self._protected_attrs:
                raise AttributeError(f"Cannot modify protected attribute '{name}'")
            # Cek apakah ini user attribute
            is_user_attr = (
                hasattr(self, "_user_attributes") and name in self._user_attributes
            )
            is_internal = self._is_internal_call()
            allow_unsafe = getattr(self, "_allow_unsafe_operations", False)
            if not is_internal and not allow_unsafe:
                raise AttributeError(
                    f"Attribute access denied: Cannot add modify attribute '{name}' directly. "
                    "Use safe_set, insert_dict, or update_dict instead."
                )
            # Safe to set attribute
            object.__setattr__(self, name, value)
            # Update ke protected_dict jika tidak diawali underscore
            if (
                hasattr(self, "_protected_dict")
                and self._protected_dict is not None
                and not name.startswith("_")
            ):
                try:
                    was_locked = self._protected_dict._locked
                    self._protected_dict._locked = False
                    self._protected_dict[name] = value
                    self._protected_dict._locked = was_locked
                except AttributeError:
                    pass
            # Track user attribute
            if hasattr(self, "_user_attributes") and not name.startswith("_"):
                self._user_attributes.add(name)

        def __delattr__(self, name: str) -> None:
            """Override delattr for protection"""
            if hasattr(self, "_protected_attrs") and name in self._protected_attrs:
                raise AttributeError(f"Cannot delete protected attribute '{name}'")

            # Cek proteksi atribut user - HANYA method internal yang boleh menghapus
            if (
                hasattr(self, "_attr_protection_enabled")
                and getattr(self, "_attr_protection_enabled", True)
                and hasattr(self, "_user_attributes")
                and name in getattr(self, "_user_attributes", set())
            ):

                # Periksa apakah ini panggilan internal yang sah
                is_internal = self._is_internal_call()
                allow_unsafe = getattr(self, "_allow_unsafe_operations", False)

                if not is_internal and not allow_unsafe:
                    raise AttributeError(
                        f"Attribute access denied: Cannot delete user attribute '{name}' directly. Use dell_dict() method instead."
                    )

            if name in getattr(self, "_method_registry", {}):
                raise AttributeError(
                    f"Method deletion denied: Cannot delete protected method '{name}'"
                )

            if name == "__dict__":
                raise AttributeError(
                    "Dictionary access denied: Cannot delete __dict__ in protected memoryawarestruct"
                )

            # Update protected dict jika ada
            if (
                hasattr(self, "_protected_dict")
                and self._protected_dict is not None
                and not name.startswith("_")
            ):
                try:
                    was_locked = self._protected_dict._locked
                    self._protected_dict._locked = False
                    del self._protected_dict[name]
                    self._protected_dict._locked = was_locked
                except (AttributeError, KeyError):
                    pass

            # Remove from user attributes tracking
            if hasattr(self, "_user_attributes") and name in self._user_attributes:
                self._user_attributes.discard(name)

            object.__delattr__(self, name)


        def __getattribute__(self, name: str) -> Any:
            """Override getattribute for method protection and controlled access"""
            if name == "__dict__":
                try:
                    dict_protection = object.__getattribute__(self, "_dict_protection_enabled")
                    if dict_protection:
                        user_attrs = {
                            k: v
                            for k, v in object.__getattribute__(self, "__dict__").items()
                            if not k.startswith("_")
                        }
                        return ReadOnlyDictView(user_attrs)
                except AttributeError:
                    pass  # Ignore if attributes not yet initialized

            try:
                attr = object.__getattribute__(self, name)

                # Protection for critical method overrides
                try:
                    method_registry = object.__getattribute__(self, "_method_registry")
                    if method_registry and name in method_registry:
                        if attr != method_registry[name]:
                            return method_registry[name]
                except AttributeError:
                    pass

                return attr

            except AttributeError as e:
                # Suggest similar attribute if not found
                try:
                    user_attrs = object.__getattribute__(self, "_user_attributes")
                    suggestions = difflib.get_close_matches(name, user_attrs, n=1, cutoff=0.7)
                    if suggestions:
                        suggestion_msg = f" Did you mean '{suggestions[0]}'?"
                    else:
                        suggestion_msg = ""
                except Exception:
                    suggestion_msg = ""

                raise AttributeError(f"Attribute '{name}' not found.{suggestion_msg}".strip()) from e


        def __getitem__(self, key: str) -> Any:
            """Allow dictionary-style access - READ ONLY"""
            # Block dictionary-style access completely
            # if getattr(self, '_dict_access_blocked', True):
            # raise AttributeError("Dictionary access denied: Dictionary-style access is completely blocked")

            try:
                return object.__getattribute__(self, replace_special_chars(key))
            except AttributeError:
                raise KeyError(key)

        def __setitem__(self, key: str, value: Any) -> None:
            """Block dictionary-style setting completely"""
            raise AttributeError(
                "Dictionary access denied: Dictionary-style modification is completely blocked"
            )

        def __delitem__(self, key: str) -> None:
            """Block dictionary-style deletion completely"""
            raise AttributeError(
                "Dictionary access denied: Dictionary-style deletion is completely blocked"
            )

        @property
        def config(self):
            """
            Read-only property to access the internal configuration instance.

            Returns:
                Any: The configuration object stored in the internal `_config` attribute.

            This property provides controlled read access to the `_config` attribute,
            which is assumed to hold the configuration data for this object. Direct
            access to `_config` is discouraged outside this interface.

            Notes:
            - This property is read-only. To modify the configuration, use specific
            methods or setters provided elsewhere (if available).
            - Bypasses `__getattr__` and other overrides by using `object.__getattribute__`.

            Raises:
                AttributeError: If the `_config` attribute is not set on the object.

            Example:
                >>> obj.config  # returns the configuration instance
            """
            return object.__getattribute__(self, "_config")

        def lock_dict(self) -> None:
            """Lock the internal dictionary to prevent modifications"""
            if self._protected_dict is not None:
                self._protected_dict.lock()

        def unlock_dict(self) -> None:
            """Permanently disabled - dictionary cannot be unlocked"""
            logger.warning("Dictionary unlock is permanently disabled for security")

        def get_dict_protection_status(self) -> dict:
            """
            Get the current dictionary protection status.

            Notes:
                If the internal `_protected_dict` is not initialized (None),
                only basic access-blocking status is returned.

            Returns:
                dict: A dictionary describing the current protection state, including:
                    - protection_enabled (bool): Whether protection is enabled.
                    - locked (bool, optional): Whether the protected dictionary is locked.
                    - authorized_methods (int, optional): Number of authorized methods.
                    - dict_access_blocked (bool): Whether dictionary access is globally blocked.
            """
            if self._protected_dict is not None:
                return {
                    "protection_enabled": True,
                    "locked": self._protected_dict._locked,
                    "authorized_methods": len(self._protected_dict._authorized_methods),
                    "dict_access_blocked": self._dict_access_blocked,
                }
            else:
                return {
                    "protection_enabled": False,
                    "dict_access_blocked": self._dict_access_blocked,
                }

        def set_struct_name(self, name: str) -> None:
            """
            Set the memoryawarestruct name for the current instance only.

            Args:
                name (str): The new name to assign to this instance's configuration.

            Raises:
                AttributeError: If the internal configuration object `_config` is not available.
            """
            self._config.set_name(name)

        def get_struct_name(self) -> str:
            """
            Get the memoryawarestruct name assigned to this instance.

            Returns:
                str: The name currently set in this instance's configuration.

            Raises:
                AttributeError: If the internal configuration object `_config` is not available.
            """
            return self._config.get_name()

        @staticmethod
        def set_global_name(name: str, config_id: str = "default") -> None:
            """
            Set the memoryawarestruct name globally for a specific configuration ID.

            Args:
                name (str): The new global memoryawarestruct name.
                config_id (str): The ID of the config instance to apply the name to. Default is "default".

            Raises:
                KeyError: If the specified configuration ID does not exist.
            """
            config = StructConfig.get_instance(config_id)
            config.set_name(name)

        @property
        def insert_dict(self):
            """
            Write-only property for inserting new key-value pairs as object attributes.

            This property allows you to assign a dictionary or a list of key-value pairs
            to add new attributes dynamically to the current object.

            Constraints:
            - Only keys that do not start with an underscore `_` are processed.
            - If a key already exists as an attribute, insertion is denied to avoid overwriting.

            Raises:
            - AttributeError: When attempting to read the property, or if a key already exists.
            - TypeError: If the assigned value is neither a dictionary nor a list.

            Example usage:
                obj.insert_dict = {"name": "Alice", "age": 30}
            """
            raise AttributeError("insert_dict is write-only and cannot be read.")


        @insert_dict.setter
        def insert_dict(self, dict_new:SelectType.Union_) -> None:
            
            if isinstance(dict_new, SelectType.Dict_):
                for key, value in dict_new.items():
                    key = replace_special_chars(key)
                    if not key.startswith("_"):
                        if hasattr(self, key):
                            raise AttributeError(
                                f"Insert failed: Key '{key}' already exists. Use update_dict instead. Use update_dict instead."
                            )
                        
                        self.safe_set(key, value, allow_override=False)
            elif isinstance(dict_new, SelectType.List_):
                data = smart_list_to_dict(dict_new)
                self.insert_dict = data
            else:
                raise TypeError("insert_dict expects a dictionary")
        
        @insert_dict.deleter
        def insert_dict(self, dict_new:SelectType.Union_) -> None:
            raise AttributeError("update_dict is write-only and cannot be read or delete.")
        
        @property
        def update_dict(self):
            """
            Write-only property for updating existing public attributes using a dictionary.

            This property allows you to assign a dictionary or a list of key-value pairs
            to update existing attributes of the object. It ensures that only attributes 
            which already exist and are public (i.e., not prefixed with `_`) can be updated.

            Constraints:
            - Only existing public keys can be updated.
            - Keys starting with an underscore `_` are ignored.

            Side Effects:
            - Creates a backup of current public attributes into `_backup_dict` before update.

            Raises:
            - AttributeError: When attempting to read the property, or if a key does not exist.
            - TypeError: If the assigned value is neither a dictionary nor a list.

            Example usage:
                obj.update_dict = {"name": "Bob"}  # Only if 'name' already exists
            """
            raise AttributeError("update_dict is write-only and cannot be read.")


        @update_dict.setter
        def update_dict(self, dict_new:SelectType.Union_) -> None:
            if isinstance(dict_new, SelectType.Dict_):
                public_attrs = {
                    k: copy.deepcopy(v)
                    for k, v in self.__dict__.items()
                    if not k.startswith("_")
                }
                object.__setattr__(self, "_backup_dict", public_attrs)
                for key, value in dict_new.items():
                    key = replace_special_chars(key)
                    if not key.startswith("_"):
                        if not hasattr(self, key):
                            raise AttributeError(
                                f"Update failed: Key '{key}' does not exist. Use insert_dict instead."
                            )
                        self.safe_set(key, value, allow_override=True)
            elif isinstance(dict_new, SelectType.List_):
                data = smart_list_to_dict(dict_new)
                self.update_dict = data
            else:
                raise TypeError("update_dict expects a dictionary")
        
        @update_dict.deleter
        def update_dict(self, dict_new:SelectType.Union_) -> None:
            raise AttributeError("update_dict is write-only and cannot be read or delete.")
    
        
        def dell_dict(self, params: str) -> bool:
            """
            Delete a user-defined attribute from the dictionary.

            Args:
                params (str): The key (attribute name) to delete.
            
            Notes:
                - Internal attributes (starting with `_`) and protected methods cannot be deleted.
                - Also updates the protected dictionary if applicable.

            Returns:
                bool: True if deletion succeeded, False otherwise.
            """

            getallmethod =  [name for name, func in inspect.getmembers(self, inspect.ismethod)]
            user_attrs = object.__getattribute__(self, "_user_attributes")
            suggestions = difflib.get_close_matches(params, user_attrs, n=1, cutoff=0.7)
            if params in getallmethod:
                raise AttributeError(f"Attribute '{params}' not found.{suggestions}".strip())
            
            # Prevent deletion of internal attributes
            params = replace_special_chars(params)
            if params.startswith("_"):
                logger.warning(f"Cannot delete internal attribute: {params}")
                return False

            # Prevent deletion of protected methods
            if params in getattr(self, "_method_registry", {}):
                logger.warning(f"Cannot delete protected method: {params}")
                return False

            user_attrs = self.get_user_attributes()

            if params in user_attrs:
                try:
                    # Update protected dict first if exists
                    if self._protected_dict is not None:
                        try:
                            was_locked = self._protected_dict._locked
                            self._protected_dict._locked = False
                            del self._protected_dict[params]
                            self._protected_dict._locked = was_locked
                        except (AttributeError, KeyError):
                            pass

                    # Remove from user attributes tracking
                    if hasattr(self, "_user_attributes"):
                        self._user_attributes.discard(params)

                    object.__delattr__(self, params)
                    logger.info(f"Successfully deleted: {params}")
                    return True
                except AttributeError:
                    logger.error(f"Cannot delete: {params}")
                    return False
            else:
                logger.error(f"Key not found: {params}")
                return False

        def restore_backup(self) -> bool:
            """
            Restore instance attributes from the last backup.

            Notes:
                - This only restores user-defined attributes (non-internal).
                - Also attempts to unlock and update protected dictionary if needed.
                - Clears current user-defined attributes before restoring.

            Returns:
                bool: True if restoration was successful, False otherwise.
            """
            if hasattr(self, "_backup_dict"):
                backup = object.__getattribute__(self, "_backup_dict")

                # Clear user attributes only
                user_attrs = list(self.get_user_attributes().keys())
                for attr in user_attrs:
                    try:
                        object.__delattr__(self, attr)
                        if self._protected_dict is not None:
                            try:
                                was_locked = self._protected_dict._locked
                                self._protected_dict._locked = False
                                del self._protected_dict[attr]
                                self._protected_dict._locked = was_locked
                            except (AttributeError, KeyError):
                                pass
                    except:
                        pass

                # Clear user attributes tracking
                if hasattr(self, "_user_attributes"):
                    self._user_attributes.clear()

                # Restore non-protected attributes from backup
                for key, value in backup.items():
                    if not key.startswith("_"):
                        self._internal_dict_update(key, value)

                logger.info("Restored from backup")
                return True
            else:
                logger.warning("No backup available")
                return False

        def reset_to_original(self) -> None:
            """
            Reset all user-defined attributes to the original state.
            """
            # Clear user attributes
            user_attrs = list(self.get_user_attributes().keys())
            for attr in user_attrs:
                try:
                    object.__delattr__(self, attr)
                    if self._protected_dict is not None:
                        try:
                            was_locked = self._protected_dict._locked
                            self._protected_dict._locked = False
                            del self._protected_dict[attr]
                            self._protected_dict._locked = was_locked
                        except (AttributeError, KeyError):
                            pass
                except:
                    pass

            # Clear user attributes tracking
            if hasattr(self, "_user_attributes"):
                self._user_attributes.clear()

            # Restore original entries
            original_entries = object.__getattribute__(self, "_original_entries")
            for key, value in original_entries.items():
                self._internal_dict_update(key, value)

            logger.info("Reset to original state")

        def safe_get(self, key: str, default: Any = None) -> Any:
            """
            Safely retrieve an attribute with a fallback default value.

            Args:
                key (str): Attribute name to fetch.
                default (Any): Value to return if attribute is not found.

            Returns:
                Any: Attribute value if found, otherwise the `default` value.
            """
            try:
                return object.__getattribute__(self, replace_special_chars(key))
            except AttributeError:
                return default

        def safe_set(self, key: str, value: Any, allow_override: bool = True) -> bool:
            """
            Safely set a user-defined attribute.

            Args:
                key (str): Attribute name to set.
                value (Any): Value to assign.
                allow_override (bool): Whether to override existing attribute. Default is True.

            Returns:
                bool: True if set succeeded, False otherwise.
            """
            key = replace_special_chars(key)
            user_attrs = object.__getattribute__(self, "_user_attributes")
            suggestions = difflib.get_close_matches(key, user_attrs, n=1, cutoff=1)
            if key in getattr(self, "_method_registry", {}):
                raise AttributeError(f"Attribute '{key}' not found.{suggestions}".strip())
            
            if key.startswith("_"):
                logger.warning(f"Cannot set internal attribute: {key}")
                return False

            if not allow_override and hasattr(self, key):
                logger.warning(f"Attribute {key} already exists and override not allowed")
                return False

            try:
                frozen_value = deep_struct_freeze(value, config_id=key)
                self._internal_dict_update(key, frozen_value)
                return True
            except AttributeError as e:
                logger.error(f"Cannot set attribute {key}: {str(e)}")
                return False

        def get_user_attributes(self) -> dict:
            """
            Get all user-defined attributes, excluding internal ones.

            Returns:
                dict: A dictionary of user-defined attributes (key-value pairs).
            """
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

        def unlock_for_maintenance(self, confirmation: str = None) -> None:
            """
            Permanently disabled method to prevent unauthorized access.

            Args:
                confirmation (str, optional): No longer accepted.

            Notes:
                This method is intentionally disabled for security reasons.
            """
            logger.warning("SECURITY: Maintenance unlock is permanently disabled")

        def lock_after_maintenance(self) -> None:
            """
            Lock the memoryawarestruct again after maintenance (already locked by default).

            Notes:
                Currently a no-op as the memoryawarestruct is always in a secured state.
            """
            logger.info("memoryawarestruct is already fully locked and secured")

        def get_protection_status(self) -> dict:
            """
            Get the complete protection status of the memoryawarestruct instance.

            Returns:
                dict: A dictionary containing:
                    - protected_attrs (int): Number of protected attributes.
                    - protected_methods (int): Number of registered protected methods.
                    - unsafe_operations_allowed (bool): If unsafe ops are enabled.
                    - user_attributes (int): Number of current user-defined attributes.
                    - user_attributes_count (int): Size of user attribute tracking set.
                    - dict_protection (dict): Status from `get_dict_protection_status`.
                    - attribute_protection (bool): Whether attribute protection is active.
                    - dict_access_completely_blocked (bool): If dict access is fully blocked.
            """
            dict_status = self.get_dict_protection_status()
            return {
                "protected_attrs": len(getattr(self, "_protected_attrs", {})),
                "protected_methods": len(getattr(self, "_method_registry", {})),
                "unsafe_operations_allowed": getattr(
                    self, "_allow_unsafe_operations", False
                ),
                "user_attributes": len(self.get_user_attributes()),
                "dict_protection": dict_status,
                "attribute_protection": getattr(self, "_attr_protection_enabled", True),
                "user_attributes_count": len(getattr(self, "_user_attributes", set())),
                "dict_access_completely_blocked": getattr(
                    self, "_dict_access_blocked", True
                ),
            }

        def __repr__(self) -> str:
            # Only show user attributes in representation
            user_attrs = self.get_user_attributes()

            if not user_attrs:
                return f"{self.get_struct_name()}()"

            output_dictionary = tuple(
                [
                    (
                        f"{k}({v})"
                        if isinstance(v, (list, dict))
                        else f"{k}({list(v)})" if isinstance(v, tuple) else f"{k}('{v}')"
                    )
                    for k, v in user_attrs.items()
                ]
            )
            return f"{self.get_struct_name()}" + str(output_dictionary).replace('"', "")


    # Factory function untuk membuat memoryawarestruct dengan konfigurasi khusus
    def create_secure_memory(
        config_id: str = "default",
        struct_name: str = "MemoryAwareStruct",
        dict_protection: bool = True,
        attr_protection: bool = True,
    ):
        """
        Factory function to create a customized Secure memoryawarestruct factory.

        This function sets up a reusable factory that generates instances of `memoryawarestruct` with
        predefined security configurations such as dictionary protection, attribute protection,
        and a specific configuration ID and name. Useful for creating scoped secure data objects
        with uniform behavior across different parts of an application.

        Args:
            config_id (str): The identifier for the shared configuration instance. Default is "default".
            struct_name (str): A label or name for this memoryawarestruct configuration, used for tracking or debugging.
            dict_protection (bool): Whether to enable protection of the internal dictionary (default: True).
            attr_protection (bool): Whether to enable protection of internal attributes (default: True).

        Returns:
            Callable[..., memoryawarestruct]: A function that, when called with keyword arguments, returns a `memoryawarestruct` instance 
            initialized with the predefined configuration.

        Example:
            >>> MySecureStruct = create_secure_memory("session", "UserSession")
            >>> obj = MySecureStruct(username="alice", role="admin")
            >>> print(obj.safe_get("username"))  # "alice"
        """
        StructConfig.get_instance(config_id).set_name(struct_name)

        def struct_factory(**kwargs):
            return memoryawarestruct(
                config_id=config_id,
                _dict_protection=dict_protection,
                _attr_protection=attr_protection,
                **kwargs,
            )

        return struct_factory


    # Context manager untuk temporary changes - DISABLED
    class SecureMemoryContext:
        """
        Context manager for safely enabling and disabling unsafe operations 
        on a memoryawarestruct instance temporarily.

        This is useful for making temporary modifications to a protected memoryawarestruct 
        while ensuring the original protection settings are restored afterward.

        Attributes:
            memoryawarestruct (Any): The struct-like object being wrapped.
            allow_unsafe (bool): Whether to allow unsafe operations within context.
            original_state (bool): Backup of the original unsafe operations flag.
            original_dict_state (bool): Backup of the protected dictionary lock state.
        """
        def __init__(self, struct_instance, allow_unsafe: bool = False):
            """
            Initialize the context manager with the memoryawarestruct instance.

            Args:
                struct_instance (Any): The struct-like object to manage.
                allow_unsafe (bool): Whether to enable unsafe operations during the context.
            """
            self.struct = struct_instance
            self.allow_unsafe = allow_unsafe
            self.original_state = None
            self.original_dict_state = None

        def __enter__(self):
            # Backup state
            self.original_state = getattr(self.struct, "_allow_unsafe_operations", False)
            if self.struct._protected_dict is not None:
                self.original_dict_state = self.struct._protected_dict._locked

            if self.allow_unsafe:
                object.__setattr__(self.struct, "_allow_unsafe_operations", True)
                if self.struct._protected_dict is not None:
                    self.struct._protected_dict.unlock()

            return self.struct

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Restore original state
            object.__setattr__(self.struct, "_allow_unsafe_operations", self.original_state)
            if (
                self.struct._protected_dict is not None
                and self.original_dict_state is not None
            ):
                if self.original_dict_state:
                    self.struct._protected_dict.lock()
    
    return ImmutableList([memoryawarestruct, create_secure_memory, SecureMemoryContext])

__main__ = __main()
create_secure_memory:Any = __main__[1]
SecureMemoryContext:Any = __main__[2]
memory:Any = __main__[0]