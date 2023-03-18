#import maya.cmds as cmds
from maya import cmds
import MASH.api as mapi
import MASHbakeInstancer as mbake;
from .faces import Faces

class Builder(object):

#region Constructor
    def __init__(self, _name):
        self.name = _name
        self.bevelSeg = 3
        self.bevelOffset = 0.02
        self.rootParent = ''
        self.nodes = []
        self.controls = []
        self.previousControl = ''
        self.activeControl = ['',0]
        self.selectionJob = -1
        self.validationJob = -1
        self.MIN_SIZE = 3
        self.MAX_SIZE = 8
        self.size = 0
        self.controlRadius = 0
        self.interactable = True
        self.visibleControls = True
        self.axis = ['x','y','z']
#endregion 

#region Build Logic
    def build(self, _size):
        """
        Drives the order of Rubik's Cube
        construction.
        """
        self.size = _size
        radiusDiv = 1.25
        self.controlRadius = self.size / radiusDiv
        
        ## Create MASH network to generate initial grid of pieces
        instancer = 'instancer'
        cube = cmds.polyCube(w = 1, h = 1, name = f'{self.name}') 
        mashNetwork = mapi.Network()
        mashNetwork.createNetwork(name = self.name, geometry = instancer)
        
        # Use primitive cube as distribution source
        cmds.connectAttr(
            str(cube[0]) + '.outMesh',
            mashNetwork.distribute + '.inputMesh')
        
        # Arrange grid based on Rubik's Cube size
        cmds.setAttr(mashNetwork.distribute + '.arrangement', 6)
        cmds.setAttr(mashNetwork.distribute + '.gridx', _size)
        cmds.setAttr(mashNetwork.distribute + '.gridy', _size)
        cmds.setAttr(mashNetwork.distribute + '.gridz', _size)
        
        # Set margin distance between instances and center overall distribution
        amplitude = _size - 1
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeX', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeY', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeZ', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.centerLinearDistribution', 1)
        
        # Bake MASH instances to Geometry
        mash = cmds.ls(type = instancer)
        cmds.select(mash)
        cmds.BakeInstancerToGeometry()
        mbake.MASHbakeInstancer(False)
        cmds.CloseFrontWindow()
        
        # Cleanup 
        cmds.delete(mash)
        cmds.delete(cube)

        # Create a list of node references      
        index = 1
        query = f'{self.name}*'

        nodes = cmds.ls(query, dag=True, transforms=True)    
        for node in nodes:
            if (not self.rootParent and self.isParent(node)): 
                            newName = f'{self.name}_parent'
                            cmds.rename(node, newName)
                            self.rootParent = newName
                            continue
            
            newName = f'{self.name}_{index}'         
            cmds.rename(node, newName) 
            self.nodes.append(newName)
            index += 1    
        
        # Visuals
        # Add edge smoothness on every piece
        self.bevelAll()
        
        # Color accoridng to face
        self.color(Faces.FRONT, [0,1,0])
        self.color(Faces.BACK, [0,0,1])
        self.color(Faces.UP, [1,1,1])
        self.color(Faces.DOWN, [1,1,0])
        self.color(Faces.LEFT, [1,0.5,0.1])
        self.color(Faces.RIGHT, [1,0,0])    

        # Center World Rotate Pivot to allow coordinated rotation
        for node in self.nodes:
            cmds.xform(node, worldSpace=True, rotatePivot=[0,0,0])      

        #Check if reference display layer already exists
        layerName = 'rubik_reference_layer'
        dispLayers = cmds.ls(type = 'displayLayer')
        layerExists = False
        if dispLayers:
            for layer in dispLayers:
                if layer == layerName:
                    layerExists = True
                    break
 
        if not layerExists:
            layer = cmds.createDisplayLayer(name = layerName)
            cmds.setAttr("{}.displayType".format(layer), 2) 
            
        # Add nodes the reference layer to prevent user interaction
        cmds.editDisplayLayerMembers(layerName, self.nodes, noRecurse=True)


        # Add Controls 
        maxLenght = 0.5 + (self.size - 2) * 0.5    
        step = -maxLenght
        for i in range(0, self.size):
            self.createControls([step,0,0], 0)
            self.createControls([0,step,0], 1)
            self.createControls([0,0,step], 2)
            step += 1

        cmds.select(clear=True)
        
        # Begin tracking input selection
        self.initSelectionJob()

    def initSelectionJob(self):
        """
        Initialises tracking job for when a control handle is selected
        in the scene. 
        ! As of now, user is required to deselect gizmos on empty space
        before selecting next one, otherwise the selection is not recognized
        by Maya. 
        """
        if cmds.scriptJob(exists=self.selectionJob):
            cmds.scriptJob(kill=self.selectionJob, force=True)

        job = cmds.scriptJob(
            killWithScene=True, 
            ct=("SomethingSelected",
            self.selectControlHandle),
            protected=True)   
        self.selectionJob = job        

    def selectControlHandle(self):
        # Prevent interaction when pieces aren't set.
        if not self.interactable: return
           
        # Confirm that only single control handle is selected,
        # otherwise clear selection
        selectedControl = cmds.ls('Control*', selection=True, flatten=True)
        
        if len(selectedControl) <= 0: return     
        if len(selectedControl) > 1:
            cmds.select(all=True, clear=True)
            return
        if selectedControl[0] == self.activeControl[0]: 
            return

        self.activeControl[0] = selectedControl[0]
        matchedNodes = []   
        
        # Find selected control and collect matching pieces    
        for control in self.controls:
            if control[0] == self.activeControl[0]: 
                self.activeControl[1] = control[3]
                matchedNodes = self.matchNodes(control[1], control[3])   
                break
        
        # Unparent old selection
        if self.previousControl:
            oldSelection = cmds.listRelatives(
                self.previousControl,
                children = True,
                type='transform')

            for match in oldSelection:
                cmds.parent(match, self.rootParent)
            
        # Parent new selection
        for match in matchedNodes:
            cmds.parent(match, selectedControl[0], s=True)               
            cmds.reorder(match, front = True ) 

        # Highlight control and show context handle
        cmds.select(selectedControl[0], noExpand=True)   
        cmds.setToolTo('RotateSuperContext')
        self.previousControl = self.activeControl[0]
        
        # Begin validating Rubik's Cube position 
        self.initControlValidation()

    def initControlValidation(self):
        """
        Starts job which tracks rotation value change.
        """
        if cmds.scriptJob(exists=self.validationJob):
            cmds.scriptJob(kill=self.validationJob, force=True)
        # Create new job for newly selected handle
      
        job = cmds.scriptJob(
            attributeChange=[f'{self.activeControl[0]}.r{self.axis[self.activeControl[1]]}',
            self.validateControlHandle],
            protected=True)
        self.validationJob = job

    def validateControlHandle(self):
        """
        Checks if rotation matches 90 degree snap
        in both directions. If not, hides all 
        control handles except current. 
        Limits global interaction.
        """
        rotAttribute = f'{self.activeControl[0]}.r{self.axis[self.activeControl[1]]}'
        angle = cmds.getAttr(rotAttribute)
        
        if angle == 0 or abs(angle) % 90 == 0:
            self.interactable = True
            print('Selected Control is Valid and Set')
        else:
            self.interactable = False     
            print ('Selected Control is Invalid ' + str(angle))
        
        if not self.interactable and self.visibleControls:
            self.visibleControls = False
            for control in self.controls:
                if control[0] == self.activeControl[0]: continue
                if cmds.getAttr(f'{control[0]}.visibility') == 1:
                    cmds.hide(control[0])
                    
        elif self.interactable:
            self.visibleControls = True
            for control in self.controls:
                cmds.showHidden(control[0])          
      
    def isParent(self, name):
        parent = cmds.listRelatives(name, parent = True)
        return not parent

    def bevelAll(self): 
        """
        Apply simple bevel on all pieces.
        [Segment] and [offset] values are exposed
        for tweaking
        """
        for node in self.nodes:
            cmds.select(node)
            cmds.polyBevel3(
                            segments=self.bevelSeg,
                            offset=self.bevelOffset,
                            chamfer=True,
                            depth=1,
                            smoothingAngle=0)      

    def color(self, _face, color): 
        """
        Vertex based paint.
        [notUndoable] flag improves performance for 
        large numbers of object. This will make
        the command not undoable regardless of 
        whether undo has been enabled or not.
        """

        faces = self.selectFacesByOrientation(_face)   
        vertices = self.selectVerticesFromFace(faces)
        cmds.select(clear=True)

        for vertex in vertices:
            cmds.polyColorPerVertex(
                                    vertex,
                                    rgb=(
                                        color[0], 
                                        color[1], 
                                        color[2]), 
                                    notUndoable=True, 
                                    colorDisplayOption=True,
                                    clamped=True)
        
        for node in self.nodes:                
            cmds.setAttr(f'{node}.displayColors', 1)
        cmds.refresh()

    def selectVerticesFromFace(self, faces):
        return cmds.polyListComponentConversion(
            faces,
            fromFace=True,
            toVertex=True) 
    
    def selectFacesByOrientation (self, face):
        """
        Constrain selection of polygon faces
        which align and translate with each
        one of the faces.
        """
        tolerance = 0   
        sequence = 0.5 + (self.size - 2) * 0.5
        value = [
            face.value[0] * sequence,
            face.value[1] * sequence,
            face.value[2] * sequence]

        cmds.select(clear = True)
        for node in self.nodes:
            if not (self.matchFace(node, face, value)): continue
            cmds.select(node + ".f[*]", add = True)   
            cmds.polySelectConstraint(
                mode = 3,
                type = 8, 
                orient = 1, 
                orientaxis = face.value, 
                orientbound = (0, tolerance))
            cmds.polySelectConstraint(dis=True)         
        return cmds.filterExpand(sm=34)

    def matchFace(self, node, face, value):
        """
        Check if each piece face matches
        with target orientation (F,B,U,D,L,R)
        """
        position = cmds.xform(
                            node, query=True,
                            translation=True,
                            worldSpace=True)                                   
        if face is Faces.FRONT:
            return round(position[2],2) == value[2]
        elif face is Faces.BACK:
            return round(position[2],2) == value[2]
        elif face is Faces.UP:
            return round(position[1],2) == value[1]
        elif face is Faces.DOWN:
            return round(position[1],2) == value[1]
        elif face is Faces.LEFT:
            return round(position[0],2) == value[0]
        elif face is Faces.RIGHT:
            return round(position[0],2) == value[0]
        else:
            return False

    def matchNodes(self, position, axis):
        """
        Similar to face matching but instead
        matches world position of pieces and 
        control handle orientation
        """
        matchedNodes = []
        position[axis] = round(position[axis], 2)
        for node in self.nodes:
            node_position = cmds.xform(
                node,
                query = True,
                translation = True,
                worldSpace = True)
            # Hotfix for precision errors during reparenting
            node_position[axis] = round(node_position[axis],2)
            if node_position[axis] != position[axis]: continue
            matchedNodes.append(node)
        return matchedNodes

    def createControls(self, position, axis):
        """
        Create circle controls and align
        with the coresponding faces
        """
        vector = [0,0,0]
        vector[axis] = 1
        control = cmds.circle( 
            object=True,
            normal=vector,
            center=position, 
            radius=self.controlRadius)
        cmds.parent(control[0], self.rootParent)
        cmds.xform(control[0], worldSpace=True, centerPivots=True)
        rotation = [0,0,0]
        tag = f'Control_{len(self.controls)}'
        cmds.rename(control[0],tag)
        self.controls.append([tag,position,rotation,axis])
#endregion

#region Save/Load State
    def getState(self):
        """
        Saves relevant variables
        into a .json file 
        """
        transforms = {          
            'node': [],
            'pos': [],
            'ori': []            
        }
        
        for node in self.nodes:
            position = cmds.xform(
                node, query = True,
                translation = True,
                worldSpace = True)    
            
            orientation = cmds.xform(
                node, query = True, 
                translation = True, 
                worldSpace = True) 
            transforms['node'].append(node)
            transforms['pos'].append(position)
            transforms['ori'].append(orientation)
       
        state = {
            'size': self.size,
            'controls': self.controls,
            'transforms': transforms
        }
        return state

    def applyState(self, state):
        """
        To be implemented
        """
        pass
#endregion

#region Set Defaults
    def cleanup(self):
        # Delete existing jobs and remove any old pieces
        if cmds.scriptJob(exists=self.selectionJob):
            cmds.scriptJob(kill=self.selectionJob, force=True)
        if cmds.scriptJob(exists=self.validationJob):
            cmds.scriptJob(kill=self.validationJob, force=True)
        old = cmds.ls(f'{self.rootParent}*', dag=True, transforms=True)
        if old: cmds.delete(old)
        self.reset()
    
    def reset(self):
        self.size = 0
        self.controlRadius = 0
        self.rootParent = ''
        self.nodes = []
        self.controls = []
        self.jobs = []
        self.validationJob = -1
        self.selectionJob = -1
        self.previousControl = ''
        self.activeControl = ['',0]
        self.selectionJob = -1
        self.validationJob = -1
        self.interactable = True
        self.visibleControls = True
#endregion
    