from abc import abstractmethod
import inspect
import os
import threading

import sublime

from .src.shared import MiniPluginMeta

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    # logger.setLevel('DEBUG')


class CompletionTrigger(object, metaclass=MiniPluginMeta):
    """Superclass for objects used to determine what types of completions to return."""

    # Dictionary used to store data about a view. The dictionary is keyed by
    # the view ID and contains ViewData objects.
    View_Data = dict()

    def __init__(self, view):
        super(CompletionTrigger, self).__init__()
        self.view = view

    @classmethod
    def _get_triggers_for_view(cls, view):
        """Returns a list of CompletionTrigger objects for the view."""
        triggers = []
        for t in CompletionTrigger.get_plugins():
            if t.view_scope_check(view) <= 0:
                continue
            elif t.view_check(view):
                triggers.append(t(view))
        return triggers

    @classmethod
    def get_triggers_for_view(cls, view):
        """Returns a list of CompletionTrigger objects for the view."""
        return ViewData.get_triggers_for_view(view)

    @classmethod
    def view_scope_check(cls, view):
        """Returns the score of the defined scope in the given view."""
        try:
            return max([view.score_selector(s.begin(), cls.view_scope())
                        for s in view.sel()])
        except ValueError:
            return view.score_selector(0, cls.view_scope())

    @classmethod
    @abstractmethod
    def view_scope(cls):
        """Return a scope to determine if a CompletionTrigger will be enabled for a view."""
        pass

    @classmethod
    def view_check(cls, view):
        """Returns True if the EntitySelector should be enabled for the given view.

        This allows for checking in addition to the scope check.

        """
        return True

    def selection_scope_check(self, locs):
        """Returns a the score for the defined scope across locs.

        Keyword arguments:
        locs - A list of the current points in the view

        """
        try:
            return max([self.view.score_selector(l, self.selection_scope()) for l in locs])
        except ValueError:
            return self.view.score_selector(l[0], self.selection_scope)

    @abstractmethod
    def selection_scope(self):
        """Return a scope to determine if a CompletionTrigger will be enabled for the current selection."""
        pass

    @abstractmethod
    def selection_check(self, prefix, locs):
        """Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        return []

    @classmethod
    def get_completion_types(cls, view, prefix, locs):
        """Return a list of completion types for the current locations."""
        completion_types = set()
        for t in cls.get_triggers_for_view(view):
            if t.selection_scope_check(locs) > 0:
                completion_types.update(t.selection_check(prefix, locs))
        return list(completion_types)


class CompletionLoader(object, metaclass=MiniPluginMeta):
    """Superclass for objects used to load completions."""

    """The value to return for a matching completer when no completions are
    found or the completions are not loaded.

    Should be overridden by extending classes.

    Use None if no completions should allow showing the built-in sublime
    completions. Use an empty list if no completions should block the
    built-in sublime completions.
    """
    EmptyReturn = ([],)

    """True to load completions asynchronously."""
    LoadAsync = False

    BeforeLoadCallbacks = []

    AfterLoadCallbacks = []

    def __new__(cls, *args, **kwargs):
        if 'Instances' not in cls.__dict__.keys():
            cls.Instances = dict()
        return super(CompletionLoader, cls).__new__(cls)

    def __init__(self, *args, **kwargs):
        """Initialize the CompletionLoader.

        This should be called by subclasses after all initialization for that
        class is done so that the instance_key property has access to all
        needed attributes.

        """
        super(CompletionLoader, self).__init__()
        self.completions = []
        self.loading = False
        self.add_instance()
        self.loader_thread = None

    @property
    def instance_key(self):
        """Return a unique key used to identify the CompletionLoader.

        This is used when caching the instance.

        """
        return self.__class__.__name__

    def add_instance(self):
        """Adds the current instance to the Instances list."""
        self.Instances[self.instance_key] = self

    @classmethod
    @abstractmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        pass

    @classmethod
    def view_scope_check(cls, view):
        """Returns the score of the defined scope in the given view."""
        try:
            return max([view.score_selector(s.begin(), cls.view_scope())
                        for s in view.sel()])
        except ValueError:
            return view.score_selector(0, cls.view_scope())

    @classmethod
    @abstractmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        pass

    @classmethod
    def view_check(cls, view):
        """Returns True if the CompletionLoader should be enabled for the given view."""
        return True

    @classmethod
    def full_view_check(cls, view):
        if cls.view_scope_check(view) <= 0:
            return False
        else:
            return cls.view_check(view)

    @classmethod
    @abstractmethod
    def instances_for_view(cls, view):
        """Returns a list of instances of the given class to be used for the given view."""
        return [cls()]

    @classmethod
    def add_loader_to_view(cls, view, **kwargs):
        l = cls(view = view, **kwargs)
        ViewData.add_loader_to_view(view, l)

    @classmethod
    def remove_loader_from_view(cls, view, **kwargs):
        l = cls(view = view, **kwargs)
        ViewData.remove_loader_from_view(view, l)

    @classmethod
    def set_view_attr(view, name, value):
        ViewData.set_view_attr(view, name, value)

    @classmethod
    def get_view_attr(view, name, default = None):
        return ViewData.get_view_attr(view, name, default)

    @classmethod
    def has_view_attr(view, name, default = None):
        return ViewData.has_view_attr(view, name)

    @classmethod
    def get_loaders_for_view(cls, view):
        """Returns a list of CompletionLoader objects for the view."""
        return [l for l in ViewData.get_loaders_for_view(view) if cls in inspect.getmro(l.__class__)]

    def get_completions(self, completion_types, completion_queue, wait = False, **kwargs):
        """Populates completion_queue for Completers with matching completion_types.

        Keyword arguments:
        completion_types - A list of the requested completion types
        completion_queue - A Queue that holds the completions from each Completer
        wait - True to force completions to load synchronously.

        This function normally will not be overridden.
        If the completer is set to load completions asynchronously (LoadAsync
        is True), a thread is started to load the completions as long as wait
        is false. If completions should be loaded synchronously, or wait is
        True, completions are loaded in the current thread. load_completions
        is called either way to load the completions.

        """
        included_completions = set(completion_types).intersection(
            set(self.completion_types()))
        if not included_completions:
            return
        logger.debug("get_completions start: %s", self)
        logger.debug('included_completions = %s', included_completions)
        logger.debug("%s.loading = %s", self, self.loading)

        # If completions are loaded but we need to refresh them, clear them
        if self.completions and self.refresh_completions():
            logger.debug("Reloading completions for %s", self)
            self.completions = set()

        # if we're not already loading completions, and they aren't loaded, load them.
        if (not self.loading) and (not self.completions):
            logger.debug("Loading completions for %s", self)
            # If completions should be loaded asynchronously, and we don't want
            # to wait on them, spawn a thread to load them.
            if self.LoadAsync and not wait:
                self.loading = True
                kwargs['included_completions'] = included_completions.copy()
                self.loader_thread = threading.Thread(target = self.load_completions, kwargs = kwargs)
                self.loader_thread.start()
            # Otherwise, load them in the current thread
            else:
                self.loading = True
                self.load_completions(
                    included_completions=included_completions.copy(), **kwargs)
                self.loading = False

        if self.loading:
            # If completions are loading and the thread is still active, return empty
            if ((self.loader_thread is None) or self.loader_thread.is_alive()):
                completion_queue.put(self.EmptyReturn)
            # Otherwise, set loading to False and return the completions
            else:
                self.loading = False
                completion_queue.put(
                    self.filter_completions(included_completions, **kwargs))
                self.loader_thread = None
        # Otherwise, just return the completions
        else:
            completion_queue.put(
                self.filter_completions(included_completions, **kwargs))
        logger.debug("get_completions stop: %s", self)
        return

    def refresh_completions(self):
        """Return True if the completions need to be reloaded."""
        return False

    @abstractmethod
    def load_completions(self, **kwargs):
        """Populate self.completions with the completions handled by this completer."""
        pass

    def filter_completions(self, completion_types, **kwargs):
        """Filters and returns the loaded completions based on the completion types requested.

        Keyword arguments:
        completion_types - The types of completions that should be returned in
                           this instance.

        This function can be overridden by extending classes, but it usually
        will not need to be. self.completions can be either a dict datatype
        or a standard iterable. Completions are cleared by this function since
        ViewCompleters usually won't cache them.

        """

        logger.debug('completion_types = %s', completion_types)
        logger.debug('self.completions = %s', self.completions)
        if isinstance(self.completions, dict):
            completions = set()
            for t in completion_types:
                try:
                    completions.update(self.completions[t])
                except KeyError:
                    logger.warning('CompletionLoader has no key "%s": %s', t, self)

        else:
            completions = set(self.completions)

        return (completions,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def add_on_before_load_callback(cls, callback):
        CompletionLoader.BeforeLoadCallbacks.append(callback)

    @classmethod
    def add_on_after_load_callback(cls, callback):
        CompletionLoader.AfterLoadCallbacks.append(callback)

    @classmethod
    def run_on_before_load_callbacks(cls, view, prefix, locations, completion_types):
        for c in CompletionLoader.BeforeLoadCallbacks:
            c(view, prefix, locations, completion_types)

    @classmethod
    def run_on_after_load_callbacks(cls, view, prefix, locations, completion_types, completions):
        for c in CompletionLoader.AfterLoadCallbacks:
            c(view, prefix, locations, completion_types, completions)


class StaticLoader(CompletionLoader):
    """CompletionLoader for completions that do not change.

    For example, a fixed list of values.

    """

    @classmethod
    def instances_for_view(cls, view):
        """Returns a list of instances of the given class to be used for the given view."""
        try:
            return [cls.Instances[cls.__name__]]
        except KeyError:
            pass
        except AttributeError:
            pass
        return [cls()]

    def __repr__(self):
        return self.__class__.__name__


class ViewLoader(CompletionLoader):
    """CompletionLoader for completions extracted from a view.

    This will normally be the current view, but it could be another view.

    """

    def __init__(self, view = None, **kwargs):
        self.view = view
        super(ViewLoader, self).__init__(**kwargs)

    def __repr__(self):
        return '%s(view = %s)' % (self.__class__.__name__, self.view.id())

    @property
    def instance_key(self):
        """Return a unique key used to identify the CompletionLoader.

        This is used when caching the instance.

        """
        return self.view.id()

    @classmethod
    def instances_for_view(cls, view):
        """
        Returns a list of instances of the given class to be used for the
        given view.

        """
        try:
            return [cls.Instances[view.id()]]
        except KeyError:
            pass
        except AttributeError:
            pass
        return [cls(view=view)]

    def refresh_completions(self):
        """Return True if the completions need to be reloaded."""
        return True


class FileLoader(CompletionLoader):
    """CompletionLoader for completions extracted from another file.

    For example, this could extract completions from an include file or it
    could extract completions from a file that is updated by an external tool.

    """

    def __init__(self, file_path = None, **kwargs):
        self.file_path = file_path
        self.last_modified_time = self.get_file_update_time()
        super(FileLoader, self).__init__(**kwargs)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.file_path)

    @property
    def instance_key(self):
        """Return a unique key used to identify the CompletionLoader.

        This is used when caching the instance.

        """
        return self.file_path

    def refresh_completions(self):
        """Return True if the completions need to be reloaded."""
        t = self.get_file_update_time()
        if t <= self.last_modified_time:
            return False
        self.last_modified_time = t
        return True

    def get_file_update_time(self):
        """Return the last time the file was modified."""
        return os.path.getmtime(self.file_path)

    @property
    def file_contents(self):
        """Reads in a file, returning each line in a list. Newlines are removed."""
        with open(self.file_path, 'r') as f:
            elements = [line.replace('\n', '') for line in f]
        return elements

    @property
    def file_contents_as_string(self):
        """Reads in a file, returning the entire contents as a string."""
        with open(self.file_path, 'r') as f:
            contents = f.read()
        return contents


class PathLoader(CompletionLoader):
    """CompletionLoader for completions extracted from a fixed path.

    For example, this could extract additional completions from multiple
    files in the same directory and cache them together.

    """

    def __init__(self, path = None, **kwargs):
        self.path = path
        super(PathLoader, self).__init__(**kwargs)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.path)

    @property
    def instance_key(self):
        """Return a unique key used to identify the CompletionLoader.

        This is used when caching the instance.

        """
        return self.path


class ViewData(object):
    """Stores data for a view."""

    Data = dict()

    def __init__(self, view):
        super(ViewData, self).__init__()
        ViewData.Data[view.id()] = self
        self.id = view.id()
        self.scope = ViewData.scope_from_view(view)
        self.update_triggers(view)
        self.loaders = set()

    @classmethod
    def get_data(cls, view):
        """Return a ViewData object for the specified view."""
        try:
            return cls.Data[view.id()]
        except KeyError:
            d = ViewData(view)
            return d

    @classmethod
    def get_triggers_for_view(cls, view):
        """Returns a list of possible EntitySelector classes for a view.

        The selectors returned here are based in part on the primary source
        scope for a view. That value is stored. If the value changes, the
        list of possible EntitySelector classes is recomputed.

        """
        d = cls.get_data(view)
        scope = ViewData.scope_from_view(view)
        hash_ = ViewData.get_triggers_hash()
        if ((d.scope != scope) or (d.triggers_hash != hash_)):
            d.scope = scope
            d.update_triggers(view)

        return d.triggers

    @classmethod
    def add_loader_to_view(cls, view, loader):
        d = cls.get_data(view)
        d.loaders.add(loader)

    @classmethod
    def remove_loader_from_view(cls, view, loader):
        d = cls.get_data(view)
        try:
            d.loaders.remove(loader)
        except KeyError:
            logger.warning('Loader %s is not assigned to the view', loader)

    @classmethod
    def get_loaders_for_view(cls, view):
        d = cls.get_data(view)
        return d.loaders

    def update_triggers(self, view):
        self.triggers_hash = ViewData.get_triggers_hash()
        self.triggers = CompletionTrigger._get_triggers_for_view(view)

    @staticmethod
    def scope_from_view(view):
        """Returns the primary source scope for a view."""
        try:
            scope = view.scope_name(view.sel()[0].begin())
        except IndexError:
            scope = view.scope_name(0)

        return scope.split(' ')[0]

    @staticmethod
    def get_triggers_hash():
        return hash(str(CompletionTrigger.get_plugins()))

    @classmethod
    def set_view_attr(cls, view, name, value):
        d = cls.get_data(view)
        setattr(d, name, value)

    @classmethod
    def get_view_attr(cls, view, name, default):
        d = cls.get_data(view)
        return getattr(d, name, default)

    @classmethod
    def has_view_attr(cls, view, name):
        d = cls.get_data(view)
        return hasattr(d, name)
