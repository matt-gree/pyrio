# pyrio
Library containing classes and functions to interact with Project Rio statfiles, web API, etc.

## rio_value.py
ID/name tables (`Tables`), the typed value objects built on them (`Character`,
`Stadium`, `PitchType`, …), and bulk translation helpers.

Resolve a raw id or name (any spelling) to a typed value object:
```python
from pyrio import Character

bowser = Character.from_raw("bowser")   # or Character.from_raw(9)
bowser.id          # 9
bowser.name        # "Bowser"
```

Per-character attributes (class, captain, stats, abilities) come from the
CSV-backed record; star-ON values via `with_superstar()`:
```python
attrs = bowser.attributes
attrs.char_class            # "Power"
attrs.is_captain            # True
attrs.slap_hit_power        # base (star-OFF)
attrs.with_superstar().slap_hit_power
```

For raw bidirectional dict translation (returns ints/strings, works on pandas
Series/DataFrames too):
```python
from pyrio import lookup, Tables

lookup(Tables.CHAR_NAME, "bowser")   # -> 9
lookup("char_name", 9)               # -> "Bowser"  (table by string name)
```


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