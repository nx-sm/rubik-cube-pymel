from maya import cmds
import json

class IO(object):

    def __init__(self):    
        self.fileFormat = "JSON Files (*.json)"
        pass
        
    def saveJson(self, data):
  
        file = cmds.fileDialog2(fileMode=0,
                                fileFilter=self.fileFormat)
        if file:
            file = open(file[0], 'w')
            json.dump(data, file)
            file.close()

    def openJson(self):
        file =cmds.fileDialog2(fileFilter=self.fileFormat, 
                               dialogStyle=2, fileMode =4)
        
        return file if file else None
       

            
	
