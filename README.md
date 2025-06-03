# 📚 MemoryAwareStruct Documentation

## 🔒 Overview

MemoryAwareStruct is a secure and protected data structure system with high-level protection against unauthorized modification. This library provides the `memory` class that can protect attributes and methods from direct access, with various integrated security mechanisms.

## ✨ Key Features

- 🛡️ **Attribute Protection**: Prevent direct modification of attributes from outside the class
- 🔐 **Dictionary Protection**: Protect `__dict__` access with an authorization system
- 🎯 **Method Registry**: Protect important methods from being overridden
- 🔄 **Smart Conversion**: Automatic conversion of mixed lists to dictionaries
- 💾 **Backup System**: Backup and restore system for data safety
- 🏗️ **Factory Pattern**: memory builder with special configuration
---

## 📖 Class Documentation

### 🏛️ Class `memory`

The main class that provides secure data structures with various protection mechanisms.

#### Constructor

```python
memory(
    __config_id: str = "default",
    __allow_unsafe_operations: bool = False,
    __dict_protection: bool = True,
    __attr_protection: bool = True,
    **entries: Union[int, str, float, list, tuple, dict, bool, bytes]
)
```

**Parameters:**
- `__config_id`: Unique identifier for the instance configuration
- `__allow_unsafe_operations`: Allow unsafe operations (not recommended)
- `__dict_protection`: Enable dictionary protection
- `__attr_protection`: Enable attribute protection
- `**entries`: Initial data for memory

#### 🔧 Properties & Methods

##### Properties
```python
config # Get a configuration instance
```

#### Safe Operations Methods
```python
def safe_get(key: str, default: Any = None) -> Any
"""Safely get an attribute value"""

def safe_set(key: str, value: Any, allow_override: bool = True) -> bool
"""Safely set an attribute value"""

def dell_dict(params: str) -> bool
"""Safely delete a dictionary key"""
```

##### Dictionary Operations
```python
@property
def update_dict # Getter for update dictionary

@update_dict.setter
def update_dict(dict_new: Union[dict, list, tuple]) -> None
"""Update an existing dictionary"""

@property 
def insert_dict # Getter for insert dictionary

@insert_dict.setter
def insert_dict(dict_new: Union[dict, list, tuple]) -> None
"""Adds a new key to the dictionary"""
```

##### Backup & Restore Methods
```python
def restore_backup() -> bool
"""Restores data from the last backup"""

def reset_to_original() -> None
"""Resets to the original data at creation"""
```

##### Utility Methods
```python
def get_user_attributes() -> dict
"""Gets only user-defined attributes"""

def get_protection_status() -> dict
"""Gets the protection status of a struct"""

def set_struct_name(name: str) -> None
"""Sets the struct name for this instance"""

def get_struct_name() -> str
"""Getting struct name"""
```

#### 📝 Usage Examples

##### Basic Usage
```python
# Create a simple memory
person = memory(name="John", age=30, city="Jakarta")
print(person)  # memory('John', 'age(30)', 'city(Jakarta)')

# Accessing data
print(person.name)  # "John"
print(person["age"])  # 30
```

##### Safe Operations
```python
# Using safe methods
person.safe_set("email", "john@example.com")
old_city = person.safe_get("city", "Unknown")

# Update multiple values
person.update_dict = {"age": 31, "city": "Bandung"}

# Insert new values
person.insert_dict = {"phone": "08123456789", "country": "Indonesia"}
```

##### Working with Nested Data
```python
# Nested structure
company = memory(
    "company1",
    name="TechCorp",
    employees=[
        {"name": "Alice", "role": "Developer"},
        {"name": "Bob", "role": "Designer"}
    ],
    location={"city": "Jakarta", "country": "Indonesia"}
)

print(company.location.city)  # "Jakarta"
```

---

### 🏭 Function ` create_secure_memory`

Factory function to create a Struct with a special configuration.

```python
def  create_secure_memory(
    config_id: str = "default",
    struct_name: str = "Struct", 
    dict_protection: bool = True,
    attr_protection: bool = True
) -> callable
```

**Parameters:**
- `config_id`: Unique configuration ID
- `struct_name`: Default name for struct
- `dict_protection`: Enable dictionary protection
- `attr_protection`: Enable attribute protection

**Returns:**
- Factory function that can be called to create struct

#### 📝 Usage Example

```python
# Create a factory with a custom configuration
UserFactory = create_secure_memory(
config_id="user_config",
struct_name="User",
dict_protection=True,
attr_protection=True
)

# Using factory
user1 = UserFactory(name="Alice", role="Admin")
user2 = UserFactory(name="Bob", role="User")

print(user1) # User('Alice', 'role(Admin)')
```

---

### 🎭 Class ` SecureMemoryContext`

Context manager for making temporary changes with security controls.

```python
class SecureMemoryContext:
def __init__(self, struct_instance, allow_unsafe: bool = False)
```

**Parameters:**
- `struct_instance`: Struct instance to modify
- `allow_unsafe`: Allow unsafe operations temporarily

#### 📝 Usage Example

```python
person = Struct("temp", name="John", age=30)

# Using context manager (DISABLED for security)
with SecureMemoryContext(person, allow_unsafe=True) as temp_struct:
# Operations that are normally blocked may be allowed
# (However this feature is disabled for security)
pass

# After leaving the context, protection is back on
```

---

## 🔐 Security Features

### Attribute Protection
- ✅ Prevent direct modification of user attributes
- ✅ Protect internal attributes from external access
- ✅ Authorization system for internal methods

### Dictionary Protection
- ✅ Block dictionary-style operations (`obj[key] = value`)
- ✅ Protected dictionary with lock system

### Method Protection
- ✅ Registry methods to prevent replacement
- ✅ Protect important methods from replacement
- ✅ Validate callers for internal operations

---

## ⚠️ Important Notes

### Security
- 🚫 Dictionary unlock is permanently disabled
- 🚫 Context manager unsafe operations are disabled
- 🚫 Maintenance unlock is disabled for security
- ✅ All modifications must be made through safe methods

### Best Practices
- 🎯 Always use `safe_set()` for attribute modification
- 🔄 Use `update_dict` to update existing data
- ➕ Use `insert_dict` to add new data
- 💾 Take advantage of backup system for data safety

### Error Handling
```python
try:
    person.name = "Direct modification" # Will error
except AttributeError as e:
    print(f"Modification blocked: {e}")
    
# The correct way
success = person.safe_set("name", "Safe modification")
if success:
    print("Modification successful")
# Or use insert_dict or update_dict 
person.update_dict = {"name": "Safe modification"}
```

---

## 🚀 Advanced Usage

### Custom Configuration
```python
# Create custom configurations
AdminFactory = create_secure_memory(
    config_id="admin_system",
    struct_name="AdminUser",
    dict_protection=True,
    attr_protection=True
)

admin = AdminFactory(
    username="admin",
    permissions=["read", "write", "delete"],
    settings={"theme": "dark", "notifications": True}
)
```

### Monitoring Protection Status
```python
status = person.get_protection_status()
print(f"Protected attributes: {status['protected_attrs']}")
print(f"Protected methods: {status['protected_methods']}")
print(f"Dictionary protection: {status['dict_protection']}")
```

### Working with Complex Data
```python
# Smart list to dict conversion
data = Struct("complex", 
users=[
["admin", {"role": "administrator", "active": True}],
["user1", {"role": "user", "active": False}]
]
)

# Automatically converted to an accessible structure
print(data.users.admin.role) # "administrator"
```

---

## 📋 Summary

MemoryAwareStruct provides a comprehensive solution for secure data structures with:

- 🛡️ **Multi-layer Protection**: Protection at attribute, method, and dictionary levels
- 🔒 **Security First**: Security as the top priority with unsafe features disabled
- 🎯 **Safe Operations**: Safe and intuitive API for data manipulation
- 🏭 **Flexible Factory**: Struct creation with customizable configurations
- 💾 **Data Integrity**: Backup and restore system to maintain data integrity

This library is ideal for applications that require data structures with high levels of security and strict access control.