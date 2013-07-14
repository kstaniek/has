#!/usr/bin/env python3

# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Generic Data Sources storage implementation

"""
from datetime import datetime, timezone
"dateutil required for conversion timestamp from iso string"
from dateutil import parser
import time

__all__ = ["timestamp", "delegate", "GenericDescriptor", "EPOCH"]

EPOCH = datetime(1970, 1, 1) #, tzinfo=timezone.utc)

"""
Generic Descriptor for getters and setters
"""
class GenericDescriptor:  # refer to page 423 form book
	def __init__(self, getter, setter=None):
		self.getter = getter
		self.setter = setter
	
	def __get__(self, instance, owner=None):
		if instance is None:
			return self
		return self.getter(instance)
	
	def __set__(self, instance, value):
		if self.setter is None:
			raise ValueError("Trying to alter readonly attribute")
		return self.setter(instance, value)
""" 
Decorators
"""
def timestamp(attribute, method_names):
	"""
	Decorate methods passed as parameters with timestamp feature
	
	params:
		attribute		: name of the attribute used as timestamp
		method_names	: list of methods that will be wrapped to update timestamp
							each time method is called (object changed)
		
	"""
	def decorator(cls):
		
		def touch(function):
			def wrapper(self, *args, **kwargs):
				self.__setattr__(attribute_name, datetime.today())
				return function(self, *args, **kwargs)
			return wrapper
		nonlocal attribute
		if not attribute.startswith("__"):
			attribute_name = "_" + cls.__name__ + "__" + attribute
			setattr(cls,attribute_name, datetime.today()) #set to localtime timestamp
		else:
			raise ValueError("Private attribute used: {0}".format(attribute))
		
		for name in method_names:
			func = getattr(cls, name)
			setattr(cls, name, touch(func))
		"""
		Wraps private attribute with setter and getter in case format conversion 
		needed in the future
		"""				
		def __last_changed_getter(self):
			return getattr(self, attribute_name)
		
		def __last_changed_setter(self, value):
			if isinstance(value, str): #assume valid datetime string
				"update from iso string"
				setattr(self, attribute_name, parser.parse(value))
				#raise NotImplementedError("dateutil must be used to import from iso")

			elif isinstance(value, int):
				"update from epoch"
				setattr(self, attribute_name, datetime.fromtimestamp(value))

			elif isinstance(value, datetime):
				"update from datetime instance"
				setattr(self, attribute_name, value)	
				#print(type(value))
			else:
				raise NotImplementedError
				
		setattr(cls, attribute, GenericDescriptor(__last_changed_getter, __last_changed_setter))
		return cls
	return decorator
			

def delegate(attribute_name, method_names):
	"""Passes the call to the attribute called attribute_name for
	every method listed in method_names.
	(See SortedListP.py for an example.)
	"""
	def decorator(cls):
		nonlocal attribute_name
		if attribute_name.startswith("__"):
			attribute_name = "_" + cls.__name__ + attribute_name
		else:
			raise ValueError("Private attribute must be used ")
			
		for name in method_names:
			setattr(cls, name, eval("lambda self, *a, **kw: "
									"self.{0}.{1}(*a, **kw)".format(
									attribute_name, name)))
		return cls
	return decorator


