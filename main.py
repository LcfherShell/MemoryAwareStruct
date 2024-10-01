import threading
import json
import sys
import re
import psutil
import asyncio
import time
import struct as st
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


def float_to_hex(f):
    return hex(st.unpack("<I", st.pack("<f", f))[0])


def hex_to_float(h):
    return st.unpack("<f", st.pack("<I", int(h, 16)))[0]


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

    def __setitem__(self, key: SelectType.String_, value: SelectType.Any_) -> None:
        if self.is_restricted(key):
            raise KeyError(f"The key '{key}' is restricted.")
        self._data[key] = value

    def __getitem__(self, key: SelectType.String_) -> SelectType.Any_:
        return self._data[key]

    def __delitem__(self, key: SelectType.String_) -> None:
        if self.is_restricted(key):
            raise KeyError(f"The key '{key}' is restricted.")
        del self._data[key]

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
            self[key] = value  # Use __setitem__ for restrictions

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


class MemoryAwareStruct(SelectType):
    """The MemoryAwareStruct class is designed to handle data in dictionaries with a memory-safe approach and multi-threaded access."""

    __slots__: SelectType.List_ = [
        "__struct_name",
        "_lock",
        "__data",
        "max_memory_usage",
        "memory_warning_triggered",
    ]

    def __init__(self, memory_default: int = None, **entries: SelectType.Dict_) -> None:
        global max_memory_usage, memory_warning_triggered
        self.__struct_name = self.__class__.__name__  # Private variable

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

        # Memulai thread untuk memantau penggunaan memori
        monitor_thread = threading.Thread(target=self.__monitor_memory__, daemon=True)
        monitor_thread.start()

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
        with self.__data.mainsession:  # Lock saat akses
            return self.__struct_name

    def set_name(self, params: SelectType.String_) -> None:
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
        """Mengambil nilai dari dictionary."""
        with self.__data.mainsession:  # Lock saat membaca data
            return self.__data.get(key, default)

    @property
    def update(self) -> None:
        pass

    @update.setter
    def update(self, dict_new: SelectType.Dict_) -> None:
        """Function for update dictionary."""
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            with self.__data.mainsession:  # Lock saat modifikasi dictionary
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__(dict_new)

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                if (
                    not self.__is_memory_full__()
                    and potential_used_memory < self.__check__()
                    and not self.__check_memory_warning_triggered__()
                ):
                    for key in dict_new.keys():
                        if key in self.__data:
                            # Jika key sudah ada, lakukan update
                            old_value = self.__data[key]
                            old_value_size = sys.getsizeof(old_value)
                            self.__data[key] = dict_new[key]  # Gunakan RestrictedDict
                            new_value_size = sys.getsizeof(dict_new[key])

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

                else:
                    if not self.__get_attribute__("max_memory_usage"):
                        memory_warning_triggered = True
                    else:
                        self.memory_warning_triggered = True
                    print("Warning: Memory full, updates restricted!")
        else:
            raise TypeError("Not Type Dict Error")

    async def async_update(self, dict_new: SelectType.Dict_) -> None:
        global max_memory_usage, memory_warning_triggered

        if isinstance(dict_new, self.Dict_):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__(dict_new)

                    # Hitung memori total setelah update
                    potential_used_memory = current_dict_size + new_dict_size

                    if (
                        not self.__is_memory_full__()
                        and potential_used_memory < self.__check__()
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
                                self.__data[key] = dict_new[
                                    key
                                ]  # Gunakan RestrictedDict
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
        """Function for insert dictionary."""
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            with self.__data.mainsession:  # Lock saat modifikasi dictionary
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__(dict_new)

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                if (
                    not self.__is_memory_full__()
                    and potential_used_memory < self.__check__()
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
        """Function for insert dictionary."""
        global max_memory_usage, memory_warning_triggered
        if isinstance(dict_new, self.Dict_):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:  # Lock saat modifikasi dictionary
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__(dict_new)

                    # Hitung memori total setelah insert
                    potential_used_memory = current_dict_size + new_dict_size
                    if (
                        not self.__is_memory_full__()
                        and potential_used_memory < self.__check__()
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
        """Function to insert a function that can be called."""
        global max_memory_usage, memory_warning_triggered
        if callable(func):
            with self.__data.mainsession:  # Lock saat menambahkan fungsi
                current_dict_size = self.__get_total_size__()
                new_dict_size = self.__get_total_size__({key: func})

                # Hitung memori total setelah insert
                potential_used_memory = current_dict_size + new_dict_size
                if (
                    not self.__is_memory_full__()
                    and potential_used_memory < self.__check__()
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
        """Function for insert dictionary."""
        global max_memory_usage, memory_warning_triggered
        if callable(func):
            async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
                # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
                with self.__data.mainsession:  # Lock saat modifikasi dictionary
                    current_dict_size = self.__get_total_size__()
                    new_dict_size = self.__get_total_size__({key: func})

                    # Hitung memori total setelah insert
                    potential_used_memory = current_dict_size + new_dict_size
                    if (
                        not self.__is_memory_full__()
                        and potential_used_memory < self.__check__()
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
        """Function to delete dictionary with key."""
        global max_memory_usage
        with self.__data.mainsession:  # Lock saat penghapusan data
            if params in self.__data:
                #kembalikan ukuran sesuai size dict dipop
                curentsize_old = self.__get_total_size__(self.__data[params])
                if not self.__get_attribute__("max_memory_usage"):
                    max_memory_usage += curentsize_old
                else:
                    self.max_memory_usage += curentsize_old
                    max_memory_usage += curentsize_old
                self.__data.pop(params)  # Menggunakan pop dari RestrictedDict
                print("success")
            else:
                print("failed")

    async def async_pop(self, params: SelectType.String_) -> None:
        """Function to delete dictionary with key."""
        global max_memory_usage
        async with asyncio.Lock():  # Menggunakan Lock saat modifikasi dictionary
            # Kunci lock untuk memastikan hanya satu thread yang dapat mengakses data
            with self.__data.mainsession:  # Lock saat penghapusan data
                if params in self.__data:
                    await asyncio.sleep(1)  # Simulasi penundaan untuk operasi asinkro
                    
                    #kembalikan ukuran sesuai size dict dipop
                    curentsize_old = self.__get_total_size__(self.__data[params])
                    if not self.__get_attribute__("max_memory_usage"):
                        max_memory_usage += curentsize_old
                    else:
                        self.max_memory_usage += curentsize_old 
                        max_memory_usage += curentsize_old
                    self.__data.pop(params)  # Menggunakan pop dari RestrictedDict
                    print("success")
                else:
                    print("failed")

    def execute_function(
        self, key: SelectType.String_, *args, **kwargs
    ) -> SelectType.Any_:
        """Function to execute a function that can be called."""
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

    def json(self) -> SelectType.String_:
        """Function to convert dictionary to json."""
        with self.__data.mainsession:  # Lock saat membaca data
            return self.__data._data.copy()

    def from_json(self, json_data: SelectType.String_) -> None:
        """Function to insert dictionary using json string."""
        data = json.loads(json_data)
        self.insert = data

    def __repr__(self) -> SelectType.String_:
        with self.__data.mainsession:  # Lock saat membaca data
            output_dictory = tuple(
                f"{k}={repr(v)}"  # Using repr for more informative output
                for k, v in self.__data.items()
            )
        return f"{self.__struct_name}({', '.join(output_dictory)})"

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
        nu = self.__get_attribute__('max_memory_usage', 0) + memory_dict_size
        # Calculate the maximum allowed memory
        max_allowed_memory = ((memory_info.total * 0.75) - round(memory_dict_size)) - nu
        return round(max_allowed_memory * 1.024)
        #return round(
            #(((memory_info.total * 0.75) - round(memory_dict_size)) - nu) * 1.024
        #)

    def __monitor_memory__(self) -> None:
        """Function to monitor memory."""
        global max_memory_usage, memory_warning_triggered
        while True:
            if self.__is_memory_full__():
                print("Warning: Full memory!")
                if not self.__get_attribute__("max_memory_usage"):
                    memory_warning_triggered = True
                else:
                    self.memory_warning_triggered = True
                    self.max_memory_usage = 0
            else:
                max_memory_usage = self.__get_max_allowed_memory__()
            # Periksa setiap 2 menit
            threading.Event().wait(120)  # 120 detik atau 2 menit

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

    def __check__(self):
        """Mengembalikan sisa memori yang diizinkan."""
        if self.__get_attribute__("max_memory_usage"):
            return self.max_memory_usage
        return max_memory_usage

    def __check_memory_warning_triggered__(self):
        """Memeriksa apakah peringatan memori telah dipicu."""
        if self.__get_attribute__("max_memory_usage"):
            return self.memory_warning_triggered
        return memory_warning_triggered

    def __get_attribute__(self, attr_name: SelectType.String_, valuedef:SelectType.Any_=None):
        # Menggunakan getattr untuk mendapatkan atribut dengan nama yang diberikan
        return getattr(self, attr_name, valuedef)

    def __can_insert_or_update__(self, size_to_add):
        """Function to check if we can insert or update based on memory limits."""
        if self.__check__() - size_to_add <= 0:
            print("Not enough memory to proceed with operation.")
            return False
        return True

    def exit_handler(self, signum, frame):
        print("Exiting program...")
        sys.exit(0)

    def set_max_runtime(self, seconds):
        signal.signal(signal.SIGABRT, self.exit_handler)
        signal.alarm(seconds)

    def set_max_memory_usage(self, megabytes):
        if resource:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (megabytes * 1024 * 1024, hard))


# Perbaiki jika user mengisi memory_default maka memoeri total kurangi, lalu jika user menginsert, update data maka perbarui memory_default dan jika memory_default 0 atau - maka tolak akses update atau insert
#
# method chaining
__all__ = ["MemoryAwareStruct"]

# Fungsi utama untuk menjalankan asinkronitas
struct = MemoryAwareStruct(key1="initial_value")
struct1 = MemoryAwareStruct(memory_default=399, key1="initial_value")


def functions():
    return 3


async def main():
    # Coba insert data baru secara asinkron
    await struct.async_insert({"key2": open("index.py", "rb").read()})

    # Coba update data yang ada secara asinkron
    await struct.async_update({"key2": ["value2", 1, "ffffffffff"]})

    # Coba update key yang tidak ada
    await struct.async_update({"key3": "value3"})

    await struct.async_insert_function("functions", functions)
    # Coba insert key baru setelah gagal update
    await struct.async_insert({"key3": "value3"})


async def main2():
    await struct1.async_insert({"key2": open("index.py", "rb").read()})
    # Coba update data yang ada secara asinkron
    await struct1.async_update({"key2": ["value2", 1, "ffffffffff"]})
    # Coba update key yang tidak ada
    await struct1.async_update({"key3": "value3"})

    await struct1.async_insert_function("functions", functions)
    # Coba insert key baru setelah gagal update
    await struct1.async_insert({"key3": "value3"})


# Contoh penggunaan
if __name__ == "__main__":
    asyncio.run(main())
    print("\n\nData 2:")
    asyncio.run(main2())
    print(struct.json())
    print(struct1.json())
    # struct.set_max_runtime(10)  # Batas waktu 10 detik
    # struct.set_max_memory_usage(1024)  # Batas memori 1 GB
