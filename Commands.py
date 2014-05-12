import sublime_plugin

from DynamicCompletions import CompletionTrigger

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class DynamicCompletionsCommand(sublime_plugin.EventListener):
    """
    

    """

    def on_query_completions(self, view, prefix, locations):
        """Returns a list of completions for the word that is being typed."""

        logger.debug('DynamicCompletions - getting completion types')
        completion_types = CompletionTrigger.get_completion_types(view, prefix, locations)
        logger.debug(completion_types)

