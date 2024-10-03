import threading
import json
import sys
import re
import psutil
import asyncio
import time
import signal

try:
    import resource
except:
    resource = None

import os

version = int(str(sys.version_info.major) + str(sys.version_info.minor))
if version > 39:
    from typing import Any, Dict, Union, TypeAlias

    class SelectType:
        Union_: TypeAlias = Union[Dict, str, tuple, int, float, bool]
        String_: TypeAlias = str
        Any_: TypeAlias = Any
        Dict_: TypeAlias = dict
        Numeric_: TypeAlias = Union[int, float]
        Boolean_: TypeAlias = bool
        List_: TypeAlias = Union[list, tuple]

else:
    from typing import Any, Dict, Union

    class SelectType:
        Union_ = Union[Dict, str, tuple, int, float, bool]
        String_ = str
        Any_ = Any
        Dict_ = dict
        Numeric_ = Union[int, float]
        Boolean_ = bool
        List_ = Union[list, tuple]


class ReadOnlyJSON:
    def __init__(self, initial_data: SelectType.Any_) -> None:
        """
        Initialize the ReadOnlyJSON with a dictionary.

        Args:
            initial_data (Any): The initial data to be secured.
        """
        # Store a deep copy of the initial data to prevent external modifications
        try:
            self._data = json.loads(json.dumps(initial_data))
        except:
            self._data = initial_data

    def __setitem__(self, key: str, value: any) -> None:
        raise AttributeError("Direct modification is not allowed.")

    def __delitem__(self, key: str) -> None:
        raise AttributeError("Direct deletion is not allowed.")

    def __dir__(self):
        """Block the dir() function."""
        raise AttributeError("The use of dir() on this class is not allowed.")

    @property
    def data(self) -> Dict[str, Any]:
        """
        Get a copy of the stored JSON data.

        Returns:
            Dict[str, Any]: A deep copy of the internal data.
        """
        return json.loads(json.dumps(self._data))

    @property
    def to_json(self) -> SelectType.String_:
        """
        Convert the stored data to a JSON string.

        Returns:
            str: JSON representation of the internal data.
        """
        return json.dumps(self._data)

    def __repr__(self) -> SelectType.String_:
        """
        Return a string representation of the ReadOnlyJSON object.

        Returns:
            str: String representation.
        """
        return f"ReadOnlyJSON({self.to_json})"

    def __str__(self) -> SelectType.String_:
        return f"ReadOnlyJSON({self.to_json})"


class RestrictedDict:
    """A dictionary that restricts certain keys and only allows specific operations."""

    def __init__(self, **entries: SelectType.Dict_):
        self._data = {}
        self.mainsession = {}
        for key, value in entries.items():
            if not self.is_restricted(key):
                self._data[key] = value
            else:
                raise KeyError(f"The key '{key}' is restricted.")

    def __setitem__(self, key: str, value: any) -> None:
        raise AttributeError(
            "Direct modification is not allowed. Use the update() method."
        )

    def __getitem__(self, key: str) -> any:
        return self._data[key]

    def __delitem__(self, key: str) -> None:
        raise AttributeError("Direct deletion is not allowed. Use the update() method.")

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __dir__(self):
        """Block the dir() function."""
        raise AttributeError("The use of dir() on this class is not allowed.")

    def __contains__(self, key: SelectType.String_) -> SelectType.Boolean_:
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def is_restricted(self, key: SelectType.String_) -> SelectType.Boolean_:
        """Defines restricted keys."""
        return key in ["__struct_name", "__lock"]

    def pop(
        self, key: SelectType.String_, default: SelectType.Any_ = None
    ) -> SelectType.Any_:
        """Remove a key and return its value or a default value."""
        if self.is_restricted(key):
            raise KeyError(f"The key '{key}' is restricted.")
        return self._data.pop(key, default)

    def update(self, other: SelectType.Dict_) -> None:
        """Update the dictionary with the provided key-value pairs."""
        for key, value in other.items():
            if isinstance(value, dict):
                # If a branch is a dictionary, wrap it in RestrictedDict
                value = RestrictedDict(**value)
            if self.is_restricted(key):
                raise KeyError(f"The key '{key}' is restricted.")
            self._data[key] = value  # Use internal storage

    def clear(self):
        self._data.clear()

    def __repr__(self) -> SelectType.String_:
        return f"{self._data}"

    def get(self, key: SelectType.String_, default: Any = None):
        """Retrieve items matching the given pattern or string."""
        if key.startswith("%") and key.endswith("%"):
            # Convert SQL LIKE to regex
            regex_pattern = key[1:-1].replace("%", ".*")  # Mengganti % dengan .*
            regex_pattern = regex_pattern.replace("?", ".")  # Mengganti ? dengan .
            regex = re.compile(f"^{regex_pattern}$")

            # Find the first item that matches
            for key, value in self.items():
                if regex.match(key):
                    return value  # Return the first matching value

        return self._data.get(key, default)  # Return default if no match is found


memory_warning_triggered: SelectType.Boolean_ = False
max_memory_usage: SelectType.Numeric_ = 0


def MemoryUsage():
    global max_memory_usage, memory_warning_triggered
    total_memory = psutil.virtual_memory().total
    satuan = ["bytes", "KB", "MB", "GB"]
    i = 0
    while total_memory >= 1024 and i < len(satuan) - 1:
        total_memory /= 1024
        i += 1
    print(f"Total memory: {total_memory:.2f} {satuan[i]}")


def getMemory(total_memory: SelectType.Numeric_) -> SelectType.String_:
    satuan = ["bytes", "KB", "MB", "GB"]
    i = 0
    while total_memory >= 1024 and i < len(satuan) - 1:
        total_memory /= 1024
        i += 1
    return satuan[i]


class MemoryAwareStruct(SelectType):
    """
    A class designed to manage structured data with memory awareness.
    
    This class allows for the secure manipulation of data in a dictionary-like structure 
    while ensuring that memory usage is monitored and controlled. The data can be accessed 
    and functions can be executed dynamically, with thread safety in mind.
    
    Args:
            memory_default (int, optional): An optional parameter to specify the default maximum 
                                            memory usage for this instance. If not provided, 
                                            the instance will rely on global memory settings.
            **entries (SelectType.Dict_): Key-value pairs to initialize the internal data structure. 
                                        This allows for flexible initialization with multiple entries.
    """
    __slots__: SelectType.List_ = [
        "__struct_name",
        "_lock",
        "__data",
        "max_memory_usage",
        "memory_warning_triggered",
    ]

    def __init__(self, memory_default: int = None, **entries: SelectType.Dict_) -> None:
        """
        Initializes the MemoryAwareStruct with optional memory constraints and initial entries.

        This constructor sets up the instance of the MemoryAwareStruct class, allowing for the 
        configuration of memory usage limits and populating the internal data structure with 
        provided entries. It also handles thread safety and initializes a global memory 
        monitoring system.

        Args:
            memory_default (int, optional): An optional parameter to specify the default maximum 
                                            memory usage for this instance. If not provided, 
                                            the instance will rely on global memory settings.
            **entries (SelectType.Dict_): Key-value pairs to initialize the internal data structure. 
                                        This allows for flexible initialization with multiple entries.

        Behavior:
            - Initializes the instance variable __struct_name with the name of the class.
            - If a memory warning has not been triggered, it invokes MemoryUsage() to start monitoring.
            - If memory_default is provided, it sets the instance's max_memory_usage and initializes
            memory_warning_triggered to False.
            - Creates an instance of RestrictedDict to hold the provided entries, ensuring that only
            allowed operations can be performed on the data.
            - Assigns a threading lock (self.__data.mainsession) to the __data attribute to manage concurrency
            and ensure thread-safe operations.
            - If the instance does not specify a max_memory_usage, it uses a global memory limit.
            - If there are existing entries in the internal data structure, it adjusts the max_memory_usage
            by deducting the size of the currently stored data.

        Raises:
            ValueError: If the provided entries exceed the allowed memory limits when the instance is created."""
        global max_memory_usage, memory_warning_triggered
        self.__struct_name = self.__class__.__name__  # Private variable
        if memory_warning_triggered == False:
            MemoryUsage()

        if memory_default:  # Memisahkan memori instance dari memori global
            self.max_memory_usage: SelectType.Numeric_ = memory_default
            self.memory_warning_triggered: SelectType.Boolean_ = False

        self.__data = RestrictedDict(**entries)  # Gunakan RestrictedDict
        self.__data.mainsession = threading.Lock()  # Lock untuk concurrency

        # Jika instance tidak memiliki batas memori, gunakan batas memori global
        if not self.__get_attribute__("max_memory_usage"):
            max_memory_usage = self.__get_max_allowed_memory__()
        else:
            if self.__data._data.__len__() > 0:
                self.max_memory_usage = self.max_memory_usage - self.__get_total_size__(
                    self.__data._data
                )
            # Kurangi batas memori global dengan memori instance
            # if not memory_warning_triggered and max_memory_usage:
            #    max_memory_usage = max_memory_usage - self.max_memory_usage
            # elif max_memory_usage<=0:
            #    max_memory_usage = self.__get_max_allowed_memory__() - self.max_memory_usage

    def __setattr__(self, name: SelectType.String_, value: SelectType.Any_) -> None:
        if name in ["__dict__"]:
            raise AttributeError(
                f"Direct updates to '{name}' are not allowed. Please use insert or update."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: SelectType.String_) -> None:
        """Prevent deletion of __dict__."""
        if name in ["__dict__", "__struct_name"]:
            raise AttributeError(f"Deleting '{name}' is not allowed.")
        super().__delattr__(name)

    def __dir__(self):
        """Block the dir() function."""
        raise AttributeError("The use of dir() on this class is not allowed.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"Error: {exc_val}")
        else:
            print("No errors occurred.")

    @property
    def __dict__(self):
        raise AttributeError("Cannot access __dict__ because not allowed.")

    @property
    def struct_name(self) -> SelectType.String_:
        """
        Property to retrieve the structure name.

        This property returns the name of the structure stored in the instance.
        It ensures thread-safe access to the structure name.

        Returns:
            SelectType.String_: The name of the structure.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe access when reading the structure name.
        """
        with self.__data.mainsession:  # Lock saat akses
            return self.__struct_name

    def set_name(self, params: SelectType.String_) -> None:
        """
        Function to set the name of the structure.

        This function allows setting the name of the structure only once. If the structure name is
        currently set to "Struct", it can be modified. Otherwise, a ValueError is raised.

        Args:
            params (SelectType.String_): The new name to set for the structure.

        Raises:
            ValueError: If the structure name has already been set to a value other than "Struct".

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe modification of the structure name.
            - Checks if the current structure name is "Struct" before allowing the modification.
        """
        with self.__data.mainsession:  # Lock saat modifikasi
            if (
                self.__struct_name == "Struct" and self.__struct_name
            ):  # Can only set once
                self.__struct_name = params
            else:
                raise ValueError("Struct name can only be set once.")

    def get(
        self, key: SelectType.String_, default: SelectType.Any_ = None
    ) -> SelectType.Any_:
        """
        Function to retrieve a value from the dictionary based on the provided key.

        This function returns the value associated with the specified key in the dictionary.
        If the key does not exist, it returns a default value.

        Args:
            key (SelectType.String_): The key whose value is to be retrieved from the dictionary.
            default (SelectType.Any_, optional): The value to return if the key is not found. Default is None.

        Returns:
            SelectType.Any_: The value associated with the key, or the default value if the key is not found.

        Behavior:
            - Utilizes a lock (`self.__data.mainsession`) to ensure thread-safe access when reading data.
        """
        with self.__data.mainsession:  # Lock saat membaca data
            return self.__data.get(key, default)

    @property
    def update(self) -> None:
        pass

    @update.setter
    def update(self, dict_new: SelectType.Dict_) -> None:
        """
        Function to update values in the dictionary based on the provided new dictionary.

        This function updates existing keys in the dictionary with new values from the provided dictionary.
        It checks for memory limits before updating the dictionary.

        Args:
            dict_new (SelectType.Dict_): The new dictionary containing values to update in the existing dictionary.

        Raises:
            TypeError: If dict_new is not of dictionary type.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe modification of the dictionary.
            - Calculates the total memory usage before and after the update to prevent exceeding memory limits.
            - If memory is full or the new memory exceeds the maximum allowed, a warning is printed and the update is restricted.
        """
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            with self.__data.mainsession:  # Lock saat modifikasi dictionary
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__(dict_new)

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                time.sleep(0.3)
                if (
                    self.__h_Data__()
                    and not self.__is_memory_full__()
                    and potential_used_memory < self.__check_max_memory_usage__()
                    and not self.__check_memory_warning_triggered__()
                ):
                    for key in dict_new.keys():
                        if key in self.__data:
                            # Jika key sudah ada, lakukan update
                            old_value = self.__data[key]
                            old_value_size = sys.getsizeof(old_value)
                            new_value_size = sys.getsizeof(dict_new)
                            # Jika instance tidak memiliki batas memori, gunakan batas memori global
                            if not self.__get_attribute__("max_memory_usage"):
                                max_memory_usage = self.__get_max_allowed_memory__()
                            else:
                                self.max_memory_usage += old_value_size - new_value_size
                                if self.max_memory_usage <= 0:
                                    self.max_memory_usage = 0
                                max_memory_usage = (
                                    self.__get_max_allowed_memory__()
                                    - self.max_memory_usage
                                )
                        time.sleep(0.02)
                        if self.__check_max_memory_usage__() > 0:
                            self.__data.update(
                                {key: dict_new[key]}
                            )  # Gunakan RestrictedDict

                else:
                    if not self.__get_attribute__("max_memory_usage"):
                        memory_warning_triggered = True
                    else:
                        self.memory_warning_triggered = True
                    print("Warning: Memory full, updates restricted!")
        else:
            raise TypeError("Not Type Dict Error")

    async def async_update(self, dict_new: SelectType.Dict_) -> None:
        """
        Asynchronous function to update values in the dictionary based on the provided new dictionary.

        This function updates existing keys in the dictionary with new values from the provided dictionary asynchronously.
        It checks for memory limits before updating the dictionary.

        Args:
            dict_new (SelectType.Dict_): The new dictionary containing values to update in the existing dictionary.

        Raises:
            TypeError: If dict_new is not of dictionary type.

        Behavior:
            - Uses an asynchronous lock to ensure thread-safe modification of the dictionary.
            - Calculates the total memory usage before and after the update to prevent exceeding memory limits.
            - If memory is full or the new memory exceeds the maximum allowed, a warning is printed and the update is restricted.
        """
        global max_memory_usage, memory_warning_triggered

        if isinstance(dict_new, self.Dict_):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__(dict_new)

                    # Hitung memori total setelah update
                    potential_used_memory = current_dict_size + new_dict_size
                    time.sleep(0.3)
                    if (
                        self.__h_Data__()
                        and not self.__is_memory_full__()
                        and potential_used_memory < self.__check_max_memory_usage__()
                        and not self.__check_memory_warning_triggered__()
                    ) and self.__can_insert_or_update__(new_dict_size):
                        await asyncio.sleep(
                            1
                        )  # Simulasi penundaan untuk operasi asinkron
                        for key in dict_new.keys():
                            if key in self.__data:
                                # Jika key sudah ada, lakukan update
                                old_value = self.__data[key]
                                old_value_size = sys.getsizeof(old_value)
                                new_value_size = sys.getsizeof(dict_new[key])

                                if not self.__get_attribute__("max_memory_usage"):
                                    max_memory_usage = self.__get_max_allowed_memory__()
                                else:
                                    self.max_memory_usage += (
                                        old_value_size - new_value_size
                                    )
                                    if self.max_memory_usage <= 0:
                                        self.max_memory_usage = 0
                                    max_memory_usage = (
                                        self.__get_max_allowed_memory__()
                                        - self.max_memory_usage
                                    )
                                time.sleep(0.02)
                                if self.__check_max_memory_usage__() > 0:
                                    self.__data.update({key: dict_new[key]})

                    else:
                        if not self.__get_attribute__("max_memory_usage"):
                            memory_warning_triggered = True
                        else:
                            # print(self.max_memory_usage, self.memory_warning_triggered)
                            self.memory_warning_triggered = True

                        print("Warning: Memory full, updates restricted!")

        else:
            raise TypeError("Not Type Dict Error")

    @property
    def insert(self):
        pass

    @insert.setter
    def insert(self, dict_new: SelectType.Dict_) -> None:
        """
        Function to insert values into the dictionary based on the provided new dictionary.

        This function adds new items to the existing dictionary from the provided dictionary.
        It checks for memory limits before inserting new items.

        Args:
            dict_new (SelectType.Dict_): The new dictionary containing values to be inserted into the existing dictionary.

        Raises:
            TypeError: If dict_new is not of dictionary type.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe modification of the dictionary.
            - Calculates the total memory usage before and after the insertion to prevent exceeding memory limits.
            - If memory is full or the new memory exceeds the maximum allowed, a warning is printed and the insertion is restricted.
        """
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            with self.__data.mainsession:  # Lock saat modifikasi dictionary
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__(dict_new)

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                time.sleep(0.3)
                if (
                    self.__h_Data__()
                    and not self.__is_memory_full__()
                    and potential_used_memory < self.__check_max_memory_usage__()
                    and not self.__check_memory_warning_triggered__()
                ) and self.__can_insert_or_update__(new_dict_size):
                    self.__data.update(dict_new)  # Menggunakan RestrictedDict
                    if not self.__get_attribute__("max_memory_usage"):
                        max_memory_usage = self.__get_max_allowed_memory__()
                    else:
                        self.max_memory_usage -= new_dict_size
                        if self.max_memory_usage <= 0:
                            self.max_memory_usage = 0
                        max_memory_usage = (
                            self.__get_max_allowed_memory__() - self.max_memory_usage
                        )
                else:
                    if not self.__get_attribute__("max_memory_usage"):
                        memory_warning_triggered = True
                    else:
                        self.memory_warning_triggered = True
        else:
            raise TypeError("Not Type Dict Error")

    async def async_insert(self, dict_new: SelectType.Dict_) -> None:
        """
        Asynchronous function to insert values into the dictionary based on the provided new dictionary.

        This function adds new items to the existing dictionary from the provided dictionary asynchronously.
        It checks for memory limits before inserting new items.

        Args:
            dict_new (SelectType.Dict_): The new dictionary containing values to be inserted into the existing dictionary.

        Raises:
            TypeError: If dict_new is not of dictionary type.

        Behavior:
            - Uses an asynchronous lock to ensure thread-safe modification of the dictionary.
            - Calculates the total memory usage before and after the insertion to prevent exceeding memory limits.
            - If memory is full or the new memory exceeds the maximum allowed, a warning is printed and the insertion is restricted.
        """
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:  # Lock saat modifikasi dictionary
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__(dict_new)

                    # Hitung memori total setelah insert
                    potential_used_memory = current_dict_size + new_dict_size
                    time.sleep(0.3)
                    if (
                        self.__h_Data__()
                        and not self.__is_memory_full__()
                        and potential_used_memory < self.__check_max_memory_usage__()
                        and not self.__check_memory_warning_triggered__()
                    ) and self.__can_insert_or_update__(new_dict_size):
                        await asyncio.sleep(
                            1
                        )  # Simulasi penundaan untuk operasi asinkron
                        self.__data.update(dict_new)  # Menggunakan RestrictedDict
                        if not self.__get_attribute__("max_memory_usage"):
                            max_memory_usage = self.__get_max_allowed_memory__()
                        else:
                            self.max_memory_usage -= new_dict_size
                            if self.max_memory_usage <= 0:
                                self.max_memory_usage = 0
                            max_memory_usage = (
                                self.__get_max_allowed_memory__()
                                - self.max_memory_usage
                            )

                    else:
                        if not self.__get_attribute__("max_memory_usage"):
                            memory_warning_triggered = True
                        else:
                            # print(self.max_memory_usage, self.memory_warning_triggered)
                            self.memory_warning_triggered = True

        else:
            raise TypeError("Not Type Dict Error")

    def insert_function(self, key: SelectType.String_, func: SelectType.Any_) -> None:
        """
        Function to insert a callable function into the dictionary, with memory usage checks.

        This function inserts a key-function pair into the dictionary, provided that the function
        is callable and memory constraints are not exceeded.

        Args:
            key (SelectType.String_): The key to associate with the function.
            func (SelectType.Any_): The function to be inserted into the dictionary.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe access to the dictionary
              during the insert operation.
            - Calculates the memory usage of the current dictionary and the potential new size after
              the insertion.
            - Checks if the memory limit is exceeded, and whether inserting the new function is allowed
              based on the available memory.
            - If the insertion is possible, the function is added to the dictionary, and memory usage is
              adjusted.
            - If the memory usage exceeds the limit, a warning (`memory_warning_triggered`) is raised.
            - Raises a `TypeError` if the provided function is not callable.

        Raises:
            TypeError: If `func` is not a callable function.
        """
        global max_memory_usage, memory_warning_triggered
        if callable(func):
            with self.__data.mainsession:  # Lock saat menambahkan fungsi
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__({key: func})

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                time.sleep(0.3)
                if (
                    self.__h_Data__()
                    and not self.__is_memory_full__()
                    and potential_used_memory < self.__check_max_memory_usage__()
                    and not self.__check_memory_warning_triggered__()
                ) and self.__can_insert_or_update__(new_dict_size):
                    self.__data[key] = func  # Menyimpan fungsi dalam RestrictedDict
                    if not self.__get_attribute__("max_memory_usage"):
                        max_memory_usage = self.__get_max_allowed_memory__()
                    else:
                        self.max_memory_usage -= new_dict_size
                        if self.max_memory_usage <= 0:
                            self.max_memory_usage = 0
                        max_memory_usage = (
                            self.__get_max_allowed_memory__() - self.max_memory_usage
                        )

                else:
                    if not self.__get_attribute__("max_memory_usage"):
                        memory_warning_triggered = True
                    else:
                        self.memory_warning_triggered = True
        else:
            raise TypeError("The parameter must be a callable function.")

    async def async_insert_function(
        self, key: SelectType.String_, func: SelectType.Any_
    ) -> None:
        """
        Asynchronous function to insert a key-function pair into the dictionary, with memory usage checks.

        This function inserts a function into the dictionary, provided the memory constraints are met and
        the function is callable. It also tracks memory usage and triggers warnings when necessary.

        Args:
            key (SelectType.String_): The key to associate with the function.
            func (SelectType.Any_): The function to be inserted into the dictionary.

        Behavior:
            - Uses `self.__data.mainsession` to ensure thread-safe access to the dictionary during the insert operation.
            - Calculates the potential memory usage after insertion and checks if it is below the allowed memory threshold.
            - If memory usage is within the limit, the function is inserted into the dictionary.
            - If memory exceeds the limit, a memory warning is triggered and the insertion is prevented.
            - Simulates asynchronous operation with `await asyncio.sleep(1)`.

        Raises:
            TypeError: If `func` is not a callable function.
        """
        global max_memory_usage, memory_warning_triggered
        if callable(func):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:  # Lock saat modifikasi dictionary
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__({key: func})

                    # Hitung memori total setelah insert
                    potential_used_memory = current_dict_size + new_dict_size
                    time.sleep(0.3)
                    if (
                        self.__h_Data__()
                        and not self.__is_memory_full__()
                        and potential_used_memory < self.__check_max_memory_usage__()
                        and not self.__check_memory_warning_triggered__()
                    ) and self.__can_insert_or_update__(new_dict_size):
                        await asyncio.sleep(
                            1
                        )  # Simulasi penundaan untuk operasi asinkron
                        self.__data[key] = func  # Menyimpan fungsi dalam RestrictedDict
                        if not self.__get_attribute__("max_memory_usage"):
                            max_memory_usage = self.__get_max_allowed_memory__()
                        else:
                            self.max_memory_usage -= new_dict_size
                            if self.max_memory_usage <= 0:
                                self.max_memory_usage = 0
                            max_memory_usage = (
                                self.__get_max_allowed_memory__()
                                - self.max_memory_usage
                            )

                    else:
                        if not self.__get_attribute__("max_memory_usage"):
                            memory_warning_triggered = True
                        else:
                            # print(self.max_memory_usage, self.memory_warning_triggered)
                            self.memory_warning_triggered = True
                    # print(self.max_memory_usage, memory_warning_triggered)
        else:
            raise TypeError("Not Type Dict Error")

    def pop(self, params: SelectType.String_) -> None:
        """
        Function to remove a key from the dictionary, adjusting memory usage accordingly.

        This function removes an item from the dictionary if the key exists, and adjusts the memory usage
        based on the size of the removed item.

        Args:
            params (SelectType.String_): The key of the item to be removed.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe removal of the item.
            - Calculates the size of the item to be removed and adjusts both the instance and global memory usage limits.
            - If the key exists, it removes the item and prints "success", otherwise prints "failed".
        """
        global max_memory_usage
        with self.__data.mainsession:  # Lock saat penghapusan data
            if params in self.__data:
                # kembalikan ukuran sesuai size dict dipop
                curentsize_old = self.__get_total_size__(self.__data[params])
                time.sleep(0.3)
                if not self.__get_attribute__("max_memory_usage"):
                    max_memory_usage += curentsize_old
                else:
                    self.max_memory_usage += curentsize_old
                    max_memory_usage += curentsize_old
                time.sleep(0.02)
                self.__data.pop(params)  # Menggunakan pop dari RestrictedDict
                print("success")
            else:
                print("failed")

    async def async_pop(self, params: SelectType.String_) -> None:
        """
        Asynchronous function to remove an item from the dictionary based on the given key.

        - This function uses an `self.__data.mainsession` to ensure that the dictionary is modified in a thread-safe manner.
        - If the key exists in the dictionary, it removes the item and adjusts the memory usage accordingly.
        - The function simulates a delay using `asyncio.sleep(1)` to represent asynchronous operations.

        Args:
            params (SelectType.String_): The key of the item to be removed from the dictionary.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure that the dictionary is not modified by multiple threads concurrently.
            - Checks if the key exists, and if found, calculates the memory size of the item to be removed and adjusts both the instance's and global memory usage limits.
            - Removes the item from the dictionary using the `pop` method.
            - If the key does not exist, it prints "failed".
        """
        global max_memory_usage
        async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
            # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
            with self.__data.mainsession:  # Lock saat penghapusan data
                if params in self.__data:
                    await asyncio.sleep(1)  # Simulasi penundaan untuk operasi asinkro

                    # kembalikan ukuran sesuai size dict dipop
                    curentsize_old = self.__get_total_size__(self.__data[params])
                    if not self.__get_attribute__("max_memory_usage"):
                        max_memory_usage += curentsize_old
                    else:
                        self.max_memory_usage += curentsize_old
                        max_memory_usage += curentsize_old
                    time.sleep(0.02)
                    self.__data.pop(params)  # Menggunakan pop dari RestrictedDict
                    print("success")
                else:
                    print("failed")

    def clear(self):
        """
        Function to clear all items from the dictionary.

        - This function uses a lock (`self.__data.mainsession`) to ensure that only one thread can clear the dictionary at a time.
        - Introduces a delay of 0.6 seconds to simulate the clearing operation.

        Behavior:
            - Acquires the `self.__data.mainsession` lock to prevent simultaneous access to the dictionary.
            - Clears all items from the dictionary using the `clear` method of `RestrictedDict`.
        """
        with self.__data.mainsession:  # Lock saat penghapusan data
            time.sleep(0.6)
            self.__data.clear()

    def reset(self):
        """
        Function to reset the dictionary by clearing all items.

        - Similar to `clear()`, but uses a shorter delay of 0.2 seconds to simulate a faster operation.
        - This function also locks the dictionary during the reset operation to ensure thread safety.

        Behavior:
            - Acquires the `self.__data.mainsession` lock to ensure thread safety.
            - Clears the dictionary using the `clear` method, effectively resetting it.
        """
        with self.__data.mainsession:  # Lock saat penghapusan data
            time.sleep(0.2)
            self.__data.clear()

    def execute_function(
        self, key: SelectType.String_, *args, **kwargs
    ) -> SelectType.Any_:
        """
        Function to execute a callable function stored in the dictionary.

        This method retrieves a function by its key from the internal data structure
        and executes it with the provided arguments. It supports both synchronous
        and asynchronous functions.

        Args:
            key (SelectType.String_): The key of the function to be executed.
            *args: Positional arguments to be passed to the function.
            **kwargs: Keyword arguments to be passed to the function.

        Returns:
            SelectType.Any_: The result of the executed function.

        Raises:
            KeyError: If the specified key is not found in the dictionary.
            TypeError: If the retrieved item is not callable.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe execution of the function.
            - Checks if the function associated with the key is callable and executes it with the provided arguments.
            - If the function is asynchronous, it handles it accordingly using `asyncio.run()`.
        """
        with self.__data.mainsession:  # Lock saat eksekusi fungsi
            if key in self.__data:
                func = self.__data[key]
                if callable(func):
                    if asyncio.iscoroutinefunction(func):
                        return asyncio.run(
                            func(*args, **kwargs)
                        )  # Handle async functions
                    return func(*args, **kwargs)  # Handle sync functions
                else:
                    raise TypeError(f"{key} is not a callable function.")
            else:
                raise KeyError(f"{key} is not found.")

    def json(self)->SelectType.Any_:
        """
        Function to convert the internal dictionary to a JSON string.

        This method retrieves a copy of the internal dictionary and converts it to
        a JSON-formatted string for easy serialization and transfer.

        Returns:
            SelectType.Any_: A JSON string representation of the internal dictionary.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe reading of the data.
            - Returns a copy of the internal data to avoid unintended modifications.
        """
        with self.__data.mainsession:  # Lock saat membaca data
            return ReadOnlyJSON(self.__data._data.copy())

    def from_json(self, json_data: SelectType.String_) -> None:
        """
        Function to populate the internal dictionary using a JSON string.

        This method takes a JSON string, parses it, and inserts the resulting
        dictionary into the internal data structure.

        Args:
            json_data (SelectType.String_): A JSON string representing the data to be inserted.

        Behavior:
            - Uses the `insert` setter to add the parsed data into the internal dictionary.
            - Raises a TypeError if the JSON string cannot be parsed into a dictionary.
        """
        data = json.loads(json_data)
        self.insert = data

    def __repr__(self) -> SelectType.String_:
        """
        Function to provide a string representation of the object.

        This method generates a string that includes the class name and its
        attributes in a format suitable for debugging and logging. The
        attributes are represented as key-value pairs, with the values
        using their `repr` representation for more informative output.

        Returns:
            SelectType.String_: A string representation of the object in the form
            'ClassName(key1=value1, key2=value2, ...)'.

        Behavior:
            - Uses a lock (`self.__data.mainsession`) to ensure thread-safe
            reading of the internal data.
            - Iterates through the internal dictionary to construct the output
            string, ensuring all items are included.
        """
        with self.__data.mainsession:  # Lock saat membaca data
            output_dictory = tuple(
                f"{k}={repr(v)}"  # Using repr for more informative output
                for k, v in self.__data.items()
            )
        return f"{self.__struct_name}({', '.join(output_dictory)})"

    def __str__(self) -> SelectType.String_:
        return self.__repr__()

    def __get_max_allowed_memory__(self) -> SelectType.Numeric_:
        """Restores 3/4 of total remaining memory."""
        memory_info = psutil.virtual_memory()
        memory_dict_size = self.__get_total_size__(self.__data._data)
        if self.__get_attribute__("max_memory_usage") and not self.__get_attribute__(
            "passessionX"
        ):
            self.max_memory_usage = self.max_memory_usage * 1.024
            self.passessionX = 1
        # Calculate nu based on max_memory_usage
        nu = self.__get_attribute__("max_memory_usage", 0) + memory_dict_size
        # Calculate the maximum allowed memory
        max_allowed_memory = ((memory_info.total * 0.75) - round(memory_dict_size)) - nu
        return round(max_allowed_memory * 1.024)
        # return round(
        # (((memory_info.total * 0.75) - round(memory_dict_size)) - nu) * 1.024
        # )

    def __is_memory_full__(self) -> SelectType.Boolean_:
        """Check if the memory is full."""
        memory_info = psutil.virtual_memory()
        memory_dict_size = self.__get_total_size__(self.__data._data)

        if not self.__get_attribute__("max_memory_usage"):
            used_memory = (memory_info.used - memory_info.available) + round(
                memory_dict_size
            )
        else:
            used_memory = (memory_info.used - memory_info.available) + (
                round(memory_dict_size) + self.max_memory_usage
            )
        return (
            (max_memory_usage <= 0)
            or (used_memory >= max_memory_usage)
            or (used_memory >= memory_info.total)
            or self.__check_memory_warning_triggered__()
        )

    def __get_total_size__(self, data=None) -> SelectType.Numeric_:
        """Function to get size of data."""
        if data is None:
            data = self.__data._data

        total_size = 0
        seen = set()
        obj_id = id(data)
        seen.add(obj_id)
        obj_size = sys.getsizeof(data)
        total_size += obj_size
        if hasattr(data, "__dict__"):
            for key, val in data.__dict__.items():
                val_id = id(val)
                if val_id not in seen:
                    seen.add(val_id)
                    total_size += self.__get_total_size__(val)

        elif hasattr(data, "__iter__"):
            if hasattr(data, "keys"):  # for dictionary
                for key in data:
                    val_id = id(data[key])
                    if val_id not in seen:
                        seen.add(val_id)
                        total_size += self.__get_total_size__(data[key])
            elif not isinstance(data, str):  # Other iterable, not string
                for item in data:
                    item_id = id(item)
                    if item_id not in seen:
                        seen.add(item_id)
                        total_size += self.__get_total_size__(item)
        return total_size

    def __check_max_memory_usage__(self):
        """Restores the remaining allowed memory."""
        if self.__get_attribute__("max_memory_usage"):
            return self.max_memory_usage
        return max_memory_usage

    def __check_memory_warning_triggered__(self):
        """Checks whether a memory warning has been triggered."""
        if self.__get_attribute__("max_memory_usage"):
            return self.memory_warning_triggered
        return memory_warning_triggered

    def __h_Data__(self):
        sizemax = self.__check_max_memory_usage__()
        getmeterBytes = getMemory(sizemax)
        if getmeterBytes in ["bytes", "KB"]:
            if getmeterBytes in ["KB"] and sizemax <= 120:
                return False
            elif getmeterBytes in ["bytes"]:
                return False
            else:
                return True
        return True

    def __get_attribute__(
        self, attr_name: SelectType.String_, valuedef: SelectType.Any_ = None
    ):
        # Menggunakan getattr untuk mendapatkan atribut dengan nama yang diberikan
        return getattr(self, attr_name, valuedef)

    def __can_insert_or_update__(self, size_to_add):
        """Function to check if we can insert or update based on memory limits."""
        if self.__check_max_memory_usage__() - size_to_add <= 0:
            print("Not enough memory to proceed with operation.")
            return False
        return True

    def exit_handler(self, signum, frame):
        print("Exiting program...")
        sys.exit(0)

    def set_max_runtime(self, seconds: SelectType.Numeric_) -> None:
        """
        Set a maximum runtime for the program. After the specified time (in seconds) has passed,
        the program will trigger the `exit_handler` to terminate or perform a cleanup.
        """
        if sys.platform == "win32":
            # Windows
            timer = threading.Timer(seconds, self.exit_handler)
            timer.start()
        else:
            # Linux
            signal.signal(signal.SIGALRM, self.exit_handler)
            signal.alarm(seconds)

    def set_max_memory_usage(self, megabytes: SelectType.Numeric_):
        """
        Set a maximum memory usage limit for the program, specified in megabytes. If the program
        exceeds this memory limit, the operating system will take appropriate action to terminate or restrict the process.
        """

        if sys.platform == "win32":
            # Windows
            import ctypes

            ctypes.cdll.msvcrt.setlimit(ctypes.c_int(2), megabytes * 1024 * 1024)
        else:
            # Linux
            resource.setrlimit(
                resource.RLIMIT_AS, (megabytes * 1024 * 1024, megabytes * 1024 * 1024)
            )


# method chaining
__all__ = ["MemoryAwareStruct"]
