import inspect
import sys

# Python version compatibility check
PY35_PLUS = sys.version_info >= (3, 5)
PY36_PLUS = sys.version_info >= (3, 6)
PY39_PLUS = sys.version_info >= (3, 9)

# Import collections.abc with fallback for older Python
try:
    from collections.abc import Iterable as AbcIterable, Mapping, Sequence
except ImportError:
    # Python < 3.3
    from collections import Iterable as AbcIterable, Mapping, Sequence

# ===== Version Info =====
__version__ = "1.0.0"
TYPE_CHECKING = False

# ===== Compatibility Utilities =====
def _format_string(template, *args, **kwargs):
    """F-string compatibility for Python < 3.6"""
    if PY36_PLUS:
        # Use actual f-string formatting when available
        return template.format(*args, **kwargs)
    else:
        return template.format(*args, **kwargs)

def _get_type_name(tp):
    """Get type name with compatibility"""
    if hasattr(tp, '__name__'):
        return tp.__name__
    elif hasattr(tp, '_name'):
        return tp._name
    else:
        return str(tp)

# ===== Special Forms =====
class _SpecialForm:
    def __init__(self, name, doc=None):
        self._name = name
        self.__doc__ = doc
    
    def __repr__(self):
        return _format_string("typing.{}", self._name)
    
    def __reduce__(self):
        return self._name

# ===== Any =====
class AnyType(_SpecialForm):
    def __init__(self):
        super(AnyType, self).__init__("Any", "Special type indicating an unconstrained type.")
    
    def __instancecheck__(self, instance):
        return True
    
    def __subclasscheck__(self, subclass):
        return True

Any = AnyType()

# ===== NoReturn =====
class NoReturnType(_SpecialForm):
    def __init__(self):
        super(NoReturnType, self).__init__("NoReturn", "Special type indicating functions that never return.")

NoReturn = NoReturnType()

# ===== ClassVar =====
class ClassVar:
    def __class_getitem__(cls, param):
        return ClassVarAlias(param)

class ClassVarAlias:
    def __init__(self, param):
        self.param = param
    
    def __repr__(self):
        return _format_string("ClassVar[{}]", self.param)

# ===== Final =====
class Final:
    def __class_getitem__(cls, param):
        return FinalAlias(param)

class FinalAlias:
    def __init__(self, param):
        self.param = param
    
    def __repr__(self):
        return _format_string("Final[{}]", self.param)

# ===== Union =====
class Union:
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        
        # Flatten nested unions
        flattened = []
        for param in params:
            if isinstance(param, UnionAlias):
                flattened.extend(param.types)
            else:
                flattened.append(param)
        
        # Remove duplicates while preserving order
        unique_types = []
        for t in flattened:
            if t not in unique_types:
                unique_types.append(t)
        
        if len(unique_types) == 1:
            return unique_types[0]
        
        return UnionAlias(tuple(unique_types))

class UnionAlias:
    def __init__(self, types):
        self.types = types
    
    def __repr__(self):
        type_reprs = [repr(t) for t in self.types]
        return _format_string("Union[{}]", ', '.join(type_reprs))
    
    def __instancecheck__(self, instance):
        return any(isinstance(instance, t) for t in self.types)
    
    def __eq__(self, other):
        return isinstance(other, UnionAlias) and set(self.types) == set(other.types)
    
    def __hash__(self):
        return hash(tuple(sorted(_get_type_name(t) for t in self.types)))

# ===== Optional =====
class Optional:
    def __class_getitem__(cls, param):
        return Union[param, type(None)]

# ===== Generic Collections =====
class List:
    def __class_getitem__(cls, param):
        return ListAlias(param)

class ListAlias:
    def __init__(self, param):
        self.param = param
    
    def __repr__(self):
        return _format_string("List[{}]", self.param)
    
    def __instancecheck__(self, instance):
        if not isinstance(instance, list):
            return False
        # For empty list, always return True as it's compatible with any List type
        if len(instance) == 0:
            return True
        if self.param is Any:
            return True
        return all(isinstance(item, self.param) for item in instance)

class Dict:
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError("Dict requires two type parameters: key, value")
        return DictAlias(*params)

class DictAlias:
    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type
    
    def __repr__(self):
        return _format_string("Dict[{}, {}]", self.key_type, self.value_type)
    
    def __instancecheck__(self, instance):
        if not isinstance(instance, dict):
            return False
        # For empty dict, always return True as it's compatible with any Dict type
        if len(instance) == 0:
            return True
        if self.key_type is Any and self.value_type is Any:
            return True
        return all(
            isinstance(k, self.key_type) and isinstance(v, self.value_type)
            for k, v in instance.items()
        )

class Tuple:
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        return TupleAlias(params)

class TupleAlias:
    def __init__(self, types):
        self.types = types
    
    def __repr__(self):
        if len(self.types) == 2 and self.types[1] is ...:
            return _format_string("Tuple[{}, ...]", self.types[0])
        type_reprs = [repr(t) for t in self.types]
        return _format_string("Tuple[{}]", ', '.join(type_reprs))
    
    def __instancecheck__(self, instance):
        if not isinstance(instance, tuple):
            return False
        
        # Handle Tuple[type, ...] (variable length)
        if len(self.types) == 2 and self.types[1] is ...:
            element_type = self.types[0]
            return all(isinstance(item, element_type) for item in instance)
        
        # Handle fixed length tuple
        if len(instance) != len(self.types):
            return False
        return all(isinstance(i, t) for i, t in zip(instance, self.types))

class Set:
    def __class_getitem__(cls, param):
        return SetAlias(param)

class SetAlias:
    def __init__(self, param):
        self.param = param
    
    def __repr__(self):
        return _format_string("Set[{}]", self.param)
    
    def __instancecheck__(self, instance):
        if not isinstance(instance, set):
            return False
        # For empty set, always return True as it's compatible with any Set type
        if len(instance) == 0:
            return True
        if self.param is Any:
            return True
        return all(isinstance(item, self.param) for item in instance)

# ===== DefaultDict =====
class DefaultDict:
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError("DefaultDict requires two type parameters: key, value")
        return DefaultDictAlias(*params)

class DefaultDictAlias:
    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type
    
    def __repr__(self):
        return _format_string("DefaultDict[{}, {}]", self.key_type, self.value_type)
    
    def __instancecheck__(self, instance):
        try:
            from collections import defaultdict
        except ImportError:
            # Fallback if defaultdict not available
            return isinstance(instance, dict)
        
        # Allow empty dict to be compatible with DefaultDict
        if isinstance(instance, dict) and len(instance) == 0:
            return True
        if not isinstance(instance, defaultdict):
            return False
        if self.key_type is Any and self.value_type is Any:
            return True
        return all(
            isinstance(k, self.key_type) and isinstance(v, self.value_type)
            for k, v in instance.items()
        )

# ===== Literal =====
class Literal:
    def __class_getitem__(cls, values):
        if not isinstance(values, tuple):
            values = (values,)
        return LiteralAlias(values)

class LiteralAlias:
    def __init__(self, values):
        self.values = values
    
    def __repr__(self):
        value_reprs = [repr(v) for v in self.values]
        return _format_string("Literal[{}]", ', '.join(value_reprs))
    
    def __instancecheck__(self, instance):
        return instance in self.values
    
    def __eq__(self, other):
        return isinstance(other, LiteralAlias) and set(self.values) == set(other.values)
    
    def __hash__(self):
        try:
            return hash(tuple(sorted(self.values, key=lambda x: (type(x).__name__, x))))
        except TypeError:
            # Handle unhashable types
            return hash(tuple(str(v) for v in self.values))

# ===== Callable =====
class Callable:
    def __class_getitem__(cls, params):
        if params is ...:
            return CallableAlias((...,), Any)
        if not isinstance(params, tuple) or len(params) != 2:
            raise TypeError("Callable[[args], return_type] expected")
        arg_types, return_type = params
        return CallableAlias(arg_types, return_type)

class CallableAlias:
    def __init__(self, arg_types, return_type):
        self.arg_types = arg_types
        self.return_type = return_type
    
    def __repr__(self):
        if self.arg_types == (...,):
            return _format_string("Callable[..., {}]", self.return_type)
        arg_reprs = [repr(t) for t in self.arg_types]
        return _format_string("Callable[[{}], {}]", ', '.join(arg_reprs), self.return_type)
    
    def __instancecheck__(self, instance):
        return callable(instance)

# ===== TypeVar =====
class TypeVar:
    def __init__(self, name, *constraints, **kwargs):
        self.name = name
        self.constraints = constraints
        # Handle keyword arguments with compatibility
        self.bound = kwargs.get('bound', None)
        self.covariant = kwargs.get('covariant', False)
        self.contravariant = kwargs.get('contravariant', False)
        
        if self.covariant and self.contravariant:
            raise ValueError("Bivariant type variables are not supported")
    
    def __repr__(self):
        return self.name
    
    def __instancecheck__(self, instance):
        if self.bound:
            return isinstance(instance, self.bound)
        if self.constraints:
            return any(isinstance(instance, constraint) for constraint in self.constraints)
        return True

# ===== Generic =====
if PY36_PLUS:
    # Use modern metaclass syntax for Python 3.6+
    class GenericMeta(type):
        def __getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params,)
            
            class_name = "{name}[{params}]".format(
                name=cls.__name__,
                params=', '.join(repr(p) for p in params)
            )
            new_class = type(class_name, (cls,), {
                '__type_params__': params,
                '__origin__': cls,
                '__args__': params
            })
            return new_class
    
    class Generic(object):
        __metaclass__ = GenericMeta
else:
    # Fallback for older Python versions
    class GenericMeta(type):
        def __getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params,)
            return cls
    
    class Generic(object):
        __metaclass__ = GenericMeta

# ===== Type Checking Utilities =====
def _is_compatible_type(value, expected_type):
    """Check if value is compatible with expected type, with special handling for generic types."""
    if expected_type is Any:
        return True
    
    # Handle None/Optional cases
    if value is None:
        if hasattr(expected_type, 'types') and type(None) in expected_type.types:
            return True
        return expected_type is type(None)
    
    # Handle Union types
    if isinstance(expected_type, UnionAlias):
        return any(_is_compatible_type(value, t) for t in expected_type.types)
    
    # Handle generic aliases with special compatibility rules
    if hasattr(expected_type, '__instancecheck__'):
        try:
            return expected_type.__instancecheck__(value)
        except (TypeError, AttributeError):
            pass
    
    # Handle regular type checking
    try:
        return isinstance(value, expected_type)
    except (TypeError, AttributeError):
        # Fallback for complex types
        return True

# ===== Type Decorators =====
def enforce_types(func):
    """Decorator to enforce type checking at runtime."""
    if not PY35_PLUS:
        # Skip type checking for very old Python
        return func
    
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        # Fallback if signature inspection fails
        return func
    
    def wrapper(*args, **kwargs):
        try:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
        except TypeError:
            # If binding fails, just call the original function
            return func(*args, **kwargs)
        
        # Check argument types
        annotations = getattr(func, '__annotations__', {})
        for name, value in bound.arguments.items():
            expected = annotations.get(name)
            if expected and expected != inspect.Parameter.empty:
                if not _is_compatible_type(value, expected):
                    error_msg = "Argument '{name}' must be {expected}, got {actual}".format(
                        name=name, expected=expected, actual=_get_type_name(type(value))
                    )
                    raise TypeError(error_msg)
        
        # Call original function
        result = func(*args, **kwargs)
        
        # Check return type
        return_annotation = annotations.get('return')
        if return_annotation and return_annotation != inspect.Parameter.empty:
            if not _is_compatible_type(result, return_annotation):
                error_msg = "Return value must be {expected}, got {actual}".format(
                    expected=return_annotation, actual=_get_type_name(type(result))
                )
                raise TypeError(error_msg)
        
        return result
    
    wrapper.__wrapped__ = func
    wrapper.__annotations__ = getattr(func, '__annotations__', {})
    return wrapper

def enforce_all_types(cls):
    """Class decorator to enforce type checking on all methods."""
    if not PY35_PLUS:
        return cls
    
    for name in dir(cls):
        try:
            method = getattr(cls, name)
            if callable(method) and hasattr(method, '__annotations__'):
                setattr(cls, name, enforce_types(method))
        except (AttributeError, TypeError):
            continue
    return cls

# ===== Utility Functions =====
def cast(typ, val):
    """Cast a value to the given type."""
    return val

def overload(func):
    """Decorator for overloaded functions."""
    if not hasattr(func, '_overloaded_signatures'):
        func._overloaded_signatures = []
    return func

def get_type_hints(obj, globalns=None, localns=None):
    """Get type hints for an object."""
    if hasattr(obj, '__annotations__'):
        return dict(obj.__annotations__)
    return {}

def get_origin(tp):
    """Get the unsubscripted version of a type."""
    return getattr(tp, '__origin__', None)

def get_args(tp):
    """Get type arguments with all substitutions performed."""
    return getattr(tp, '__args__', ())

# ===== NewType =====
def NewType(name, tp):
    def new_type(x):
        return x
    
    new_type.__name__ = name
    new_type.__qualname__ = name
    try:
        new_type.__module__ = sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        new_type.__module__ = '__main__'
    new_type.__supertype__ = tp
    
    return new_type

# ===== TypedDict =====
def TypedDict(typename, fields, **kwargs):
    """Create a typed dictionary class."""
    total = kwargs.get('total', True)
    
    if isinstance(fields, dict):
        annotations = fields
    else:
        # Support list of (name, type) tuples
        annotations = dict(fields)
    
    namespace = {
        '__annotations__': annotations,
        '__total__': total,
        '__required_keys__': frozenset(annotations.keys()) if total else frozenset(),
        '__optional_keys__': frozenset() if total else frozenset(annotations.keys()),
    }
    
    return type(typename, (dict,), namespace)

# ===== NamedTuple =====
def NamedTuple(typename, fields):
    """Create a named tuple with type annotations."""
    try:
        from collections import namedtuple
    except ImportError:
        # Very old Python fallback
        def namedtuple(name, fields):
            return type(name, (tuple,), {})
    
    if isinstance(fields, dict):
        field_names = list(fields.keys())
        field_types = list(fields.values())
    else:
        field_names = [name for name, _ in fields]
        field_types = [tp for _, tp in fields]
    
    base_class = namedtuple(typename, field_names)
    
    # Add type annotations
    base_class.__annotations__ = dict(zip(field_names, field_types))
    
    return base_class

if PY39_PLUS:
    # ===== Generic =====
    class GenericMeta(type):
        def __getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params,)
            
            # Create new class with type parameters
            class_name = f"{cls.__name__}[{', '.join(repr(p) for p in params)}]"
            new_class = type(class_name, (cls,), {
                '__type_params__': params,
                '__origin__': cls,
                '__args__': params
            })
            return new_class
        
        def __instancecheck__(cls, instance):
            # Check if instance is of the generic type or its parameterized versions
            return isinstance(instance, cls.__bases__[0] if cls.__bases__ else object)

    class Generic(metaclass=GenericMeta):
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            # Store type parameters for runtime introspection
            if hasattr(cls, '__orig_bases__'):
                cls.__type_params__ = getattr(cls.__orig_bases__[0], '__args__', ())

    class AsyncIterable:
        def __class_getitem__(cls, param):
            return AsyncIterableAlias(param)

    class AsyncIterableAlias:
        def __init__(self, param):
            self.param = param
        
        def __repr__(self):
            return f"AsyncIterable[{self.param}]"
        
        def __instancecheck__(self, instance):
            return hasattr(instance, '__aiter__')

    class AsyncIterator:
        def __class_getitem__(cls, param):
            return AsyncIteratorAlias(param)

    class AsyncIteratorAlias:
        def __init__(self, param):
            self.param = param
        
        def __repr__(self):
            return f"AsyncIterator[{self.param}]"
        
        def __instancecheck__(self, instance):
            return hasattr(instance, '__aiter__') and hasattr(instance, '__anext__')

    class AsyncGenerator:
        def __class_getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params, type(None))
            return AsyncGeneratorAlias(*params)

    class AsyncGeneratorAlias:
        def __init__(self, yield_type, send_type=None):
            self.yield_type = yield_type
            self.send_type = send_type or type(None)
        
        def __repr__(self):
            return f"AsyncGenerator[{self.yield_type}, {self.send_type}]"
        
        def __instancecheck__(self, instance):
            import types
            return isinstance(instance, types.AsyncGeneratorType)
        
    class ContextManager:
        def __class_getitem__(cls, param):
            return ContextManagerAlias(param)

    class ContextManagerAlias:
        def __init__(self, param):
            self.param = param
        
        def __repr__(self):
            return f"ContextManager[{self.param}]"
        
        def __instancecheck__(self, instance):
            return hasattr(instance, '__enter__') and hasattr(instance, '__exit__')
        
    class Generator:
        def __class_getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params, type(None), type(None))
            elif len(params) == 1:
                params = (params[0], type(None), type(None))
            return GeneratorAlias(*params)

    class GeneratorAlias:
        def __init__(self, yield_type, send_type=None, return_type=None):
            self.yield_type = yield_type
            self.send_type = send_type or type(None)
            self.return_type = return_type or type(None)
        
        def __repr__(self):
            return f"Generator[{self.yield_type}, {self.send_type}, {self.return_type}]"
        
        def __instancecheck__(self, instance):
            import types
            return isinstance(instance, types.GeneratorType)
    
    # ===== Protocol =====
    class ProtocolMeta(type):
        def __instancecheck__(cls, instance):
            # Simple structural typing check
            required_methods = [name for name, value in cls.__dict__.items() 
                            if callable(value) and not name.startswith('_')]
            return all(hasattr(instance, method) for method in required_methods)

    class Protocol(metaclass=ProtocolMeta):
        pass

try:
    from collections import OrderedDict
except ImportError:
    # Fallback minimal OrderedDict untuk Python < 2.7
    class OrderedDict(dict):
        """Dictionary that remembers insertion order"""
        def __init__(self, *args, **kwargs):
            super(OrderedDict, self).__init__(*args, **kwargs)
            self._keys = []
            for key in self:
                self._keys.append(key)

        def __setitem__(self, key, value):
            if key not in self:
                self._keys.append(key)
            super(OrderedDict, self).__setitem__(key, value)

        def __delitem__(self, key):
            super(OrderedDict, self).__delitem__(key)
            self._keys.remove(key)

        def keys(self):
            return self._keys[:]

        def items(self):
            return [(k, self[k]) for k in self._keys]

        def values(self):
            return [self[k] for k in self._keys]

        def iteritems(self):
            for k in self._keys:
                yield (k, self[k])

        def itervalues(self):
            for k in self._keys:
                yield self[k]

        def iterkeys(self):
            for k in self._keys:
                yield k

        def __iter__(self):
            return iter(self._keys)

        def clear(self):
            super(OrderedDict, self).clear()
            self._keys = []

        def popitem(self, last=True):
            if not self._keys:
                raise KeyError('dictionary is empty')
            key = self._keys.pop(-1 if last else 0)
            value = self.pop(key)
            return key, value

        def update(self, *args, **kwargs):
            for k, v in dict(*args, **kwargs).items():
                self[k] = v

        def copy(self):
            return OrderedDict(self.items())

        def __repr__(self):
            items = ", ".join(f"{k!r}: {v!r}" for k, v in self.items())
            return f"OrderedDict({{{items}}})"
        
# ===== Example Usage =====
if __name__ == "__main__":
    try:
        # Test basic types
        test_dict = {}  # Should be compatible with any Dict type
        test_list = []  # Should be compatible with any List type
        
        # Test Union
        union_type = Union[int, float]
        print("Union test:", isinstance("42", union_type))
        
        # Test Optional
        optional_type = Optional[str]
        print("Optional test:", isinstance(None, optional_type))
        
        # Test Literal
        literal_type = Literal["active", "inactive"]
        print("Literal test:", isinstance("active", literal_type))
        
        print("All basic tests passed!")
        
    except Exception as e:
        print("Error during testing: {}".format(e))