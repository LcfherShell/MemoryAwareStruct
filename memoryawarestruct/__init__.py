import os, sys
path, filename = os.path.split(__file__)
sys.path.insert(0, path)
from .utils.typedata import *
from .utils.middleware import ProtectedDict, ReadOnlyDictView, ProtectedAttribute, metaClass, replace_special_chars, smart_list_to_dict
from .core.memory import memory, create_secure_memory, SecureMemoryContext