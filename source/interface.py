from maya import cmds

class Interface(object):
    """
    View component that is responsbile in presenting
    all parameters as 2D elements
    """

    def __init__(self, windowAttr, commands):
        
        self.window = cmds.window(
            title=windowAttr['title'],
            widthHeight=windowAttr['dimensions'])   
        
        self.sizeValue = 2
        self.setLayout(commands)
        cmds.showWindow(self.window)
   

    def setLayout(self, commands):
              
        cmds.columnLayout(adjustableColumn=True)
        cmds.separator( style='single')     

        cmds.intSliderGrp(commands['sizeRef'], label='Size', field=True, minValue = commands['minSize'], 
                        maxValue = commands['maxSize'], 
                        value = 3 )

        cmds.separator( style='single')
        cmds.button(label='Build!', command=commands['build'])
        cmds.button(label='Save State', command= commands['save'])

