# project_rio_lib
Library containing classes and functions to interact with Project Rio statfiles, web API, etc.

## lookup.py
Utility to access various stats and attributes of characters. Useful for things like setting parameters for web requests, since those require the character ID number. To get the character ID of a character like Bowser, you would do something like:
```python
from lookup import Lookup, LookupDicts
l = Lookup()

l.lookup(LookupDicts.CHAR_NAME, 'bowser', auto_print=True)
```
The lookup works in either direction, so you can pass it the integer value or the string representation of the lookup target.


## api.py
This file contains functionality to retrieve data from the web API, and will eventually be able to handle local statfiles efficiently as well. It contains a class RequestBuilder that can be used to more easily generate the parameters for an api fetch request (see examples.py for sample use).

## data_handler.py
This contains classes that allow for processing and conversion of data. The WebHandler class takes data retrieved from the web API and handles it, allowing for it to be used in pandas dataframes, and converted to a variety of formats (CSV, SQLite, Parquet). 

## draw/
This directory is a set of basic plotting functions for plotting MSSB stadiums. In the future the hope is to make it more well-featured, but for now it is serviceable for basic plotting. Drawing Mario Stadium is as simple as:
```python
from draw import draw_stadium
import matplotlib.pyplot as plt

draw_stadium.draw_stad('draw/mario_stadium')
plt.show()
```

## helpers.py

This file contains primarily data manipulation or calculation functions. It will likely be refactored later.