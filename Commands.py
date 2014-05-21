import collections
from queue import Queue
import threading

import sublime_plugin

from DynamicCompletions import CompletionTrigger, CompletionLoader

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class DynamicCompletionsCommand(sublime_plugin.EventListener):
    """General command for loading completions."""

    def on_query_completions(self, view, prefix, locations):
        """Returns a list of completions for the word that is being typed."""
        logger.debug('DynamicCompletions - getting completion types')
        completion_types = CompletionTrigger.get_completion_types(view, prefix, locations)
        logger.debug(completion_types)

        if not completion_types:
            return

        CompletionLoader.run_on_before_load_callbacks(view,
                                                      prefix,
                                                      locations,
                                                      completion_types)

        loaders = set()
        for c in CompletionLoader.get_plugins():
            # logger.debug('c = %s', c)
            # logger.debug('c.instances_for_view(view) = %s', c.instances_for_view(view))
            loaders.update(c.instances_for_view(view))

        # loaders = CompletionLoader.get_loaders_for_view(view)
        logger.debug('loaders = %s', loaders)

        if not loaders:
            return

        completion_queue = Queue()
        self.add_completions_to_queue(view, completion_queue, completion_types, loaders)

        completions = self.get_completions_from_queue(completion_queue)
        # logger.debug(completions)

        CompletionLoader.run_on_after_load_callbacks(view,
                                                     prefix,
                                                     locations,
                                                     completion_types,
                                                     completions)
        
        return completions

    def add_completions_to_queue(self, view, completion_queue, completion_types, loaders):
        """Adds completions to the completion_queue.

        Keyword arguments:
        completion_queue - A Queue for holding the completions returned by the Completers
        completion_types - A set of the types of completions needed 
        view - A sublime.View object for the current file

        """
        logger.debug('Adding completions to the queue')
        # Build a queue of completers that can be run asynchronously (i.e. Not ViewCompleters)
        async_loaders = Queue()
        sync_loaders = []
        for l in loaders:
            if l.LoadAsync:
                async_loaders.put(l)
            else:
                sync_loaders.append(l)

        def process_completers(completers, completion_types, completion_queue):
            """For each completer, add its completions to the completion_queue.

            Keyword arguments:
            completers - A Queue of Completer objects
            completion_types - A set of the types of completions requested
            completion_queue - The completions returned by a completer are added to this Queue
            view - A sublime.View object

            This function is structured so that it can be called from a thread
            for concurrent processing. It cannot be used to process 
            ViewCompleters due to the fact that commands obtain some type of 
            thread lock on the view.

            """
            logger.debug('process_completers running')
            proceed = True
            while not completers.empty():
                try:
                    c = completers.get(timeout = 0.1)
                except Empty:
                    proceed = False
                else:
                    c.get_completions(completion_types = completion_types,
                                      completion_queue = completion_queue)
                    completers.task_done()

            logger.debug('process_completers stopping')

            return

        # If there are more than 3 asynchronous completers, run them asynchronously.
        # Otherwise, run them in the current thread
        if async_loaders.qsize() > 3:
            for i in range(2):
                t = threading.Thread(target = process_completers, 
                                     args = (async_loaders, completion_types,
                                             completion_queue))
                t.start()
        else:
            process_completers(async_loaders, completion_types,
                               completion_queue)

        # Process the synchronous completers in this thread
        for l in sync_loaders:
            l.get_completions(completion_types = completion_types,
                              completion_queue = completion_queue,
                              view = view)

        # Wait for all the asynchronous completers to be processed
        async_loaders.join()

    def get_completions_from_queue(self, completion_queue):
        """Returns a tuple of (completions, flags) based on the contents of the completion_queue.

        Keyword arguments:
        completion_queue - A Queue object. The items in the queue should be 
        either a collection of completions or a tuple of (completions, flags).

        """
        logger.debug('Getting completions from the queue')
        completions = []
        flags = 0
        while not completion_queue.empty():
            c = completion_queue.get(block = False)
            if isinstance(c, tuple):
                try:
                    flags = flags | c[1]
                except IndexError:
                    pass
                if (isinstance(c[0], collections.Iterable)):
                    completions.extend(c[0])
            elif isinstance(c, collections.Iterable):
                completions.extend(c)
        completions.sort()
        return (completions, flags)

