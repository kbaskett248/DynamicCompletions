# Dynamic Completions

A [Sublime Text 3](http://www.sublimetext.com/) package providing a unified 
framework for creating advanced completion packages.

## Features

*   Separate the trigger for showing completions from the completions that are
    loaded.
*   Multiple trigger classes can be filtered by the overall view scope, the
    current selection scope, and any other necessary checking.
*   Completion loading classes can be filtered based on the view.
*   Completion loading classes can control whether or not the default Sublime 
    completions are returned in addition to their own completions.
*   Completions can be kept in memory or reloaded each time they are triggered.
*   Completions can be loaded synchronously or asynchronously.
*   Completions can be filtered after they are loaded based on the desired 
    completion types.
*   Completion loading classes can be defined as unique for the following
    identifiers:
    *   Static: Only one instance of this loader will exist. Return the same
        completions every time.
    *   View: An instance is unique to a view.
    *   File: An instance is unique to a file. Completions are reloaded if the 
        file is updated.
    *   Path: An instance is unique to a path.

# Installation

## Package Control

Install [Package Control](http://wbond.net/sublime_packages/package_control). Add this repository (https://bitbucket.org/kbaskett/dynamiccompletions) to Package Control. DynamicCompletions will show up in the packages list.

## Manual installation

Go to the "Packages" directory (`Preferences` > `Browse Packages…`). Then download or clone this repository:

https://bitbucket.org/kbaskett/dynamiccompletions.git

