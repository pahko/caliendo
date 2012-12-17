from hashlib import sha1
import inspect

from caliendo import util
from caliendo import config
from caliendo import call_descriptor
from caliendo import counter

USE_CALIENDO = config.should_use_caliendo( )
CONFIG       = config.get_database_config( )

if USE_CALIENDO:
    if 'mysql' in CONFIG['ENGINE']:
        from caliendo.db.mysql import *
    else:
        from caliendo.db.sqlite import *
        
class Wrapper( object ):
  """
  The Caliendo facade. Extends the Python object. Pass the initializer an object
  and the Facade will wrap all the public methods. Built-in methods
  (__somemethod__) and private methods (__somemethod) will not be copied. The
  Facade actually maintains a reference to the original object's methods so the
  state of that object is manipulated transparently as the Facade methods are
  called. 
  """
  last_cached = None

  def delete_last_cached(self):
      """
      Deletes the last object that was cached by this instance of caliendo's Facade
      """
      return delete_io( self.last_cached )

  def get_hash(self, args, trace_string, kwargs ):
      return (str(frozenset(util.serialize_args(args))) + "\n" +
                              str( counter.counter.get_from_trace( trace_string ) ) + "\n" +
                              str(frozenset(util.serialize_args(kwargs))) + "\n" +
                              trace_string + "\n" )

  def wrap( self, method_name ):
    """
    This method actually does the wrapping. When it's given a method to copy it
    returns that method with facilities to log the call so it can be repeated.

    :param str method_name: The name of the method precisely as it's called on
    the object to wrap.

    :rtype: lambda function.
    """
    def append_and_return( self, *args, **kwargs ):
      trace_string      = method_name + " "
      for f in inspect.stack():
        trace_string = trace_string + f[1] + " " + f[3] + " "

      to_hash                = self.get_hash(args, trace_string, kwargs)
      call_hash              = sha1( to_hash ).hexdigest()
      cd                     = call_descriptor.fetch( call_hash )
      if cd:
        return cd.returnval
      else:
        returnval = (self.__store__['methods'][method_name])(*args, **kwargs)
        cd = call_descriptor.CallDescriptor( hash      = call_hash,
                                             stack     = trace_string,
                                             method    = method_name,
                                             returnval = returnval,
                                             args      = args,
                                             kwargs    = kwargs )
        cd.save()
        self.last_cached = call_hash
        return cd.returnval

    return lambda *args, **kwargs: Facade( append_and_return( self, *args, **kwargs ) )

  def __getattr__( self, key ):
    if key not in self.__store__:
        raise Exception( "Key, " + str( key ) + " has not been set in the facade! Method is undefined." )
    return self.__store__[ key ]

  def __init__( self, o ):

    self.__store__ = dict()
    store = self.__store__
    store[ 'methods' ] = {}

    for method_name, member in inspect.getmembers( o ):
        if USE_CALIENDO:
            if inspect.ismethod(member) or inspect.isfunction(member) or inspect.isclass(member):
                self.__store__['methods'][method_name] = eval( "o." + method_name )
                ret_val                                = self.wrap( method_name )
                self.__store__[ method_name ]          = ret_val
            elif '__' not in method_name:
                pass
        else:
            self.__store__[ method_name ]              = eval( "o." + method_name )

def __is_primitive(var):
  primitives = ( float, long, str, int, dict, list, unicode )
  for primitive in primitives:
      if type( var ) == primitive:
          return True
  return False

def Facade( some_instance ):
    """
    Top-level interface to the Facade functionality. Determines what to return when passed arbitrary objects.

    :param mixed some_instance: Anything.
    
    """
    if not USE_CALIENDO:
        return some_instance # Just give it back.
    else:
        if __is_primitive(some_instance):
            return some_instance
        return Wrapper( some_instance )