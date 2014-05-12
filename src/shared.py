from abc import ABCMeta
import inspect

class MiniPluginMeta(ABCMeta):
    """A metaclass to be used for Sublime Mini Plugins. 

    A Mini Plugin is a class that extends functionality for a framework.
    This metaclass provides the following features:
    1. The metaclass extends ABCMeta, so methods can be made abstract.
    2. The metaclass implements __lt__, so it can be sorted. Sorting is done
       by class name.
    3. Each class that is not abstract registers itself with the original base
       class. The classes are registered using the register method. If 
       additional registering needs to be done, the method can be overridden,
       but you should always call the parent's register method.
    4. A list of the non_abstract child classes can be obtained using the 
       get_plugins method.

    """

    def __init__(cls, classname, bases, dictionary):
        """Instantiates a MiniPlugin class.

        Creates the Plugins list if this is the base MiniPlugin class.
        Registers this class if it is not abstract.

        """
        super(MiniPluginMeta, cls).__init__(classname, bases, dictionary)
        if not [c for c in bases if isinstance(c, MiniPluginMeta)]:
            cls.Plugins = []
        if not inspect.isabstract(cls):
            cls.register()
    
    def __lt__(self, other):
        """Return True if this class is less than other.

        The class name is used to compare. If other has a __repr__ method, it
        is used for comparison. Otherwise, __name__ is used.

        """
        try:
            return self.__name__ < other.__repr__()
        except TypeError:
            return self.__name__ < other.__name__

    def register(cls):
        """Register the class with it's parent.

        If additional registration needs to be done by extending classes, this
        method can be overridden. However, you should always call the parent
        classes register method to ensure that the class is registered with 
        the top most parent class.

        """
        cls.Plugins.append(cls)

    def unregister(cls):
        """Unregister the current class with it's parent.

        This should be used whenever a class should be removed from the 
        available plugins.

        """
        cls.Plugins.remove(cls)

    def get_plugins(cls):
        """Return a list of plugins of the same type."""
        return [c for c in cls.Plugins if cls in inspect.getmro(c)]

    def get_defined_classes(cls, globals_):
        """Return a list of classes defined in the current file that are instances of the given class.
        
        This method can be combined with the unregister method to unregister
        any classes defined in a file that are subclasses of the given class.

        """
        file_ = globals_['__file__']
        return [c for c in globals_.values() if 
                (inspect.isclass(c) and 
                 (inspect.getfile(c) == file_) and 
                 (cls in inspect.getmro(c))
                )]
