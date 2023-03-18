from maya import cmds
from importlib import reload
from inspect import getmodule
from source.file_manager import IO
from source.interface import Interface
from source.builder import Builder
reload(getmodule(Builder))
reload(getmodule(Interface))
reload(getmodule(IO))

def saveFile(*args):
    if not builder : return
    fileManager.saveJson(builder.getState())

def build(*args):
    builder.cleanup()
    size = cmds.intSliderGrp(commandAttr['sizeRef'] , query = True, value=True)
    builder.build(size)

cmds.selectPref(useDepth=True)
cmds.undoInfo(state=False)
cmds.manipRotateContext('Rotate', edit=True, mode=2, 
                        snap=True, snapValue=10) 

windowAttr = {
            'title': 'Rubik_Cube',
            'dimensions': (300,100)
            }

commandAttr = {
            'minSize': 2,
            'maxSize': 8,
            'size': 2,
            'sizeRef': 'size',
            'save': saveFile,
            'build': build
            }

builder = Builder(windowAttr['title'])
fileManager = IO()
ui = Interface(windowAttr, commandAttr)


 
