from abc import abstractmethod
import threading

import sublime

from .src.shared import MiniPluginMeta

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class CompletionTrigger(object, metaclass = MiniPluginMeta):
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


class CompletionLoader(object, metaclass = MiniPluginMeta):
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

    def __init__(self):
        super(CompletionLoader, self).__init__()
        self.completions = completions
        self.loading = False

    @classmethod
    @abstractmethod
    def completion_types():
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
    def get_loaders_for_view(cls, view):
        """Returns a list of CompletionLoader objects for the view."""
        loaders = set()
        for l in CompletionLoader.get_plugins():
            if l.view_scope_check(view) <= 0:
                continue
            elif l.view_check(view):
                loaders.append(t(view))
        return loaders

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
        included_completions = set(completion_types).intersection(set(self.CompletionTypes))
        if not included_completions:
            return

        logger.debug('included_completions = %s', included_completions)

        # If completions exist, put them on the queue
        if self.completions:
            completion_queue.put(self.filter_completions(included_completions, **kwargs))
            return
        # Otherwise, if we're not already loading completions, load them.
        elif not self.loading:
            # If completions should be loaded asynchronously, and we don't want 
            # to wait on them, spawn a thread to load them.
            if self.LoadAsync and not wait:
                self.loading = True
                kwargs['included_completions'] = included_completions
                self.loader_thread = threading.Thread(target = self.load_completions, kwargs = kwargs)
                self.loader_thread.start()
            # Otherwise, load them in the current thread
            else:
                self.loading = True
                self.load_completions(included_completions = included_completions, **kwargs)
                self.loading = False

        if self.loading:
            # If completions are loading and the thread is still active, return empty
            if ((self.loader_thread is None) or self.loader_thread.is_alive()):
                completion_queue.put(self.EmptyReturn)
                return
            # Otherwise, set loading to False
            else:
                self.loading = False
        # Add completions to queue and return
        completion_queue.put(self.filter_completions(included_completions, **kwargs))
        return

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
        if isinstance(self.completions, dict):
            completions = set()
            for t in completion_types:
                completions.update(self.completions[t])
        else:
            completions = set(self.completions)

        return (completions,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)


class ViewData(object):
    """Stores data for a view."""

    Data = dict()

    def __init__(self, view):
        super(ViewData, self).__init__()
        ViewData.Data[view.id()] = self
        self.id = view.id()
        self.scope = ViewData.scope_from_view(view)
        self.update_triggers(view)
        self.update_triggers(view)
        self.loaders = dict()

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
        if ((d.scope != scope) or 
            (d.triggers_hash != hash_)):
            d.scope = scope
            d.update_triggers(view)

        return d.triggers

    @classmethod
    def get_loaders_for_view(cls, view, type_ = None):
        d = cls.get_data(view)
        if type_ is None:
            return list(d.loaders.values())
        else:
            try:
                return d.loaders[type_]
            except KeyError:
                logger.warning('No CompletionLoaders if type %s installed', type_)
                return []

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
        
        
