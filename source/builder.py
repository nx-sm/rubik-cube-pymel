from maya import cmds
import MASH.api as mapi
import MASHbakeInstancer as mbake
from faces import Faces
import logging

MIN_SIZE = 3
MAX_SIZE = 8


def select_vertices_from_face(faces):
    """
    Converts face components to vertex components.
    """
    return cmds.polyListComponentConversion(
        faces,
        fromFace=True,
        toVertex=True
    )


def match_face(node, face, value):
    """
    Check if each piece face matches with target orientation (F, B, U, D, L, R).
    """
    position = cmds.xform(
        node,
        query=True,
        translation=True,
        worldSpace=True
    )
    rounded_position = [round(coord, 2) for coord in position]

    return rounded_position == value if face in [Faces.FRONT, Faces.BACK, Faces.UP, Faces.DOWN, Faces.LEFT,
                                                 Faces.RIGHT] else False


def is_parent(name):
    """
    Checks if the given name has a parent in the scene.
    Returns True if no parent is found, otherwise False.
    """
    return not cmds.listRelatives(name, parent=True)


class Builder:

    def __init__(self, name="Builder"):
        self.name = name
        self.bevel_segments = 3
        self.bevel_offset = 0.02
        self.root_parent = ''
        self.nodes = []
        self.controls = []
        self.previous_control = ''
        self.active_control = ['', 0]
        self.selection_job = -1
        self.validation_job = -1
        self.size = 0
        self.control_radius = 0
        self.interactable = True
        self.visible_controls = True
        self.axis = ['x', 'y', 'z']

    def build(self, size):
        """
        Drives the order of Rubik's Cube construction.
        """
        self.size = size
        radius_divisor = 1.25
        self.control_radius = self.size / radius_divisor
        instancer = 'instancer'
        cube = cmds.polyCube(w=1, h=1, name=self.name)
        mash_network = mapi.Network()
        mash_network.createNetwork(name=self.name, geometry=instancer)

        # Use primitive cube as distribution source
        cmds.connectAttr(str(cube[0]) + '.outMesh', mashNetwork.distribute + '.inputMesh')

        # Arrange grid based on Rubik's Cube size
        cmds.setAttr(mashNetwork.distribute + '.arrangement', 6)
        cmds.setAttr(mashNetwork.distribute + '.gridx', self.size)
        cmds.setAttr(mashNetwork.distribute + '.gridy', self.size)
        cmds.setAttr(mashNetwork.distribute + '.gridz', self.size)

        # Set margin distance between instances and center overall distribution
        amplitude = self.size - 1
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeX', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeY', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.gridAmplitudeZ', amplitude)
        cmds.setAttr(mashNetwork.distribute + '.centerLinearDistribution', 1)

        # Bake MASH instances to Geometry
        mash = cmds.ls(type=instancer)
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
            if not self.root_parent and is_parent(node):
                new_name = f'{self.name}_parent'
                cmds.rename(node, new_name)
                self.root_parent = new_name
                continue

            new_name = f'{self.name}_{index}'
            cmds.rename(node, new_name)
            self.nodes.append(new_name)
            index += 1

            # Visuals
        # Add edge smoothness on every piece
        self.bevel_all()

        # Color accoridng to face
        self.color(Faces.FRONT, [0, 1, 0])
        self.color(Faces.BACK, [0, 0, 1])
        self.color(Faces.UP, [1, 1, 1])
        self.color(Faces.DOWN, [1, 1, 0])
        self.color(Faces.LEFT, [1, 0.5, 0.1])
        self.color(Faces.RIGHT, [1, 0, 0])

        # Center World Rotate Pivot to allow coordinated rotation
        for node in self.nodes:
            cmds.xform(node, worldSpace=True, rotatePivot=[0, 0, 0])

            # Check if reference display layer already exists
        layer_name = 'rubik_reference_layer'
        disp_layers = cmds.ls(type='displayLayer')
        layer_exists = False
        if disp_layers:
            for layer in disp_layers:
                if layer == layer_name:
                    layer_exists = True
                    break

        if not layer_exists:
            layer = cmds.createDisplayLayer(name=layer_name)
            cmds.setAttr("{}.displayType".format(layer), 2)

            # Add nodes the reference layer to prevent user interaction
        cmds.editDisplayLayerMembers(layer_name, self.nodes, noRecurse=True)

        # Add Controls
        max_lenght = 0.5 + (self.size - 2) * 0.5
        step = -max_lenght
        for i in range(0, self.size):
            self.create_controls([step, 0, 0], 0)
            self.create_controls([0, step, 0], 1)
            self.create_controls([0, 0, step], 2)
            step += 1

        cmds.select(clear=True)

        # Begin tracking input selection
        self.init_selection_job()

    def init_selection_job(self):
        """
        Initialises tracking job for when a control handle is selected
        in the scene.
        ! As of now, user is required to deselect gizmos on empty space
        before selecting next one, otherwise the selection is not recognized
        by Maya.
        """
        if cmds.scriptJob(exists=self.selection_job):
            cmds.scriptJob(kill=self.selection_job, force=True)

        job = cmds.scriptJob(
            killWithScene=True,
            ct=("SomethingSelected",
                self.select_control_handle),
            protected=True)
        self.selection_job = job

    def select_control_handle(self):
        # Prevent interaction when pieces aren't set
        if not self.interactable:
            return

        selected_control = cmds.ls('Control*', selection=True, flatten=True)

        if len(selected_control) == 0 or len(selected_control) > 1:
            cmds.select(clear=True)
            return

        if selected_control[0] == self.active_control[0]:
            return

        self.active_control[0] = selected_control[0]
        matched_nodes = []

        # Find selected control and collect matching pieces
        for control in self.controls:
            if control[0] == self.active_control[0]:
                self.active_control[1] = control[3]
                matched_nodes = self.match_nodes(control[1], control[3])
                break

        # Un-parent old selection
        if self.previous_control:
            old_selection = cmds.listRelatives(self.previous_control, children=True, type='transform')
            for match in old_selection:
                cmds.parent(match, self.root_parent)

        # Parent new selection
        for match in matched_nodes:
            cmds.parent(match, selected_control[0], s=True)
            cmds.reorder(match, front=True)

        # Highlight control and show context handle
        cmds.select(selected_control[0], noExpand=True)
        cmds.setToolTo('RotateSuperContext')
        self.previous_control = self.active_control[0]

        # Begin validating Rubik's Cube position
        self.init_control_validation()

    def init_control_validation(self):
        """
        Starts job which tracks rotation value change.
        """
        if cmds.scriptJob(exists=self.validation_job):
            cmds.scriptJob(kill=self.validation_job, force=True)

        self.validation_job = cmds.scriptJob(
            attributeChange=[
                f'{self.active_control[0]}.r{self.axis[self.active_control[1]]}',
                self.validate_control_handle
            ],
            protected=True
        )

    def validate_control_handle(self):
        """
        Checks if rotation matches 90-degree snap in both directions.
        If not, hides all control handles except current.
        Limits global interaction.
        """
        rot_attribute = f'{self.active_control[0]}.r{self.axis[self.active_control[1]]}'
        angle = cmds.getAttr(rot_attribute)

        self.interactable = angle == 0 or abs(angle) % 90 == 0
        logging.info(f'Selected Control is {"Valid and Set" if self.interactable else f"Invalid {angle}"}')

        if self.interactable:
            self.visible_controls = True
            for control in self.controls:
                cmds.showHidden(control[0])
        elif not self.interactable and self.visible_controls:
            self.visible_controls = False
            for control in self.controls:
                if control[0] == self.active_control[0]:
                    continue
                if cmds.getAttr(f'{control[0]}.visibility') == 1:
                    cmds.hide(control[0])

    def bevel_all(self):
        """
        Apply simple bevel on all pieces.
        Segment and offset values are exposed for tweaking.
        """
        for node in self.nodes:
            cmds.polyBevel3(
                segments=self.bevel_segments,
                offset=self.bevel_offset,
                chamfer=True,
                depth=1,
                smoothingAngle=0,
                o=node
            )

    def color(self, face: Faces, color_value):
        """
        Vertex-based paint.
        The 'notUndoable' flag improves performance for large numbers of objects.
        This will make the command not undoable regardless of whether undo has been enabled or not.
        """
        faces = self.select_faces_by_orientation(face)
        vertices = select_vertices_from_face(faces)
        cmds.select(clear=True)

        for vertex in vertices:
            cmds.polyColorPerVertex(
                vertex,
                rgb=(color_value[0], color_value[1], color_value[2]),
                notUndoable=True,
                colorDisplayOption=True,
                clamped=True
            )

        for node in self.nodes:
            cmds.setAttr(f'{node}.displayColors', 1)
        cmds.refresh()

    def select_faces_by_orientation(self, face):
        """
        Constrain selection of polygon faces which align and translate with each face.
        """
        tolerance = 0
        sequence = 0.5 + (self.size - 2) * 0.5
        value = [coord * sequence for coord in face.value]

        cmds.select(clear=True)
        for node in self.nodes:
            if not match_face(node, face, value):
                continue
            cmds.select(f"{node}.f[*]", add=True)
            cmds.polySelectConstraint(
                mode=3,
                type=8,
                orient=1,
                orientaxis=face.value,
                orientbound=(0, tolerance)
            )
            cmds.polySelectConstraint(dis=True)

        return cmds.filterExpand(sm=34)

    def match_nodes(self, position, axis):
        """
        Matches world position of pieces and control handle orientation.
        """
        matched_nodes = []
        position[axis] = round(position[axis], 2)

        for node in self.nodes:
            node_position = cmds.xform(
                node,
                query=True,
                translation=True,
                worldSpace=True
            )
            node_position[axis] = round(node_position[axis], 2)

            if node_position[axis] == position[axis]:
                matched_nodes.append(node)

        return matched_nodes

    def create_controls(self, position, axis):
        """
        Create circle controls and align with the corresponding faces.
        """
        vector = [0, 0, 0]
        vector[axis] = 1
        control = cmds.circle(
            object=True,
            normal=vector,
            center=position,
            radius=self.control_radius
        )
        control_tag = f'Control_{len(self.controls)}'
        cmds.rename(control[0], control_tag)
        cmds.parent(control_tag, self.root_parent)
        cmds.xform(control_tag, worldSpace=True, centerPivots=True)

        self.controls.append([control_tag, position, [0, 0, 0], axis])

    def get_state(self):
        """
        Saves relevant variables into a dictionary, suitable for serialization to JSON.
        """
        transforms = {'node': [], 'pos': [], 'ori': []}

        for node in self.nodes:
            position = cmds.xform(node, query=True, translation=True, worldSpace=True)
            orientation = cmds.xform(node, query=True, translation=True, worldSpace=True)
            transforms['node'].append(node)
            transforms['pos'].append(position)
            transforms['ori'].append(orientation)

        return {'size': self.size, 'controls': self.controls, 'transforms': transforms}

    def apply_state(self, state):
        """
        To be implemented
        """
        pass

    def cleanup(self):
        """
        Deletes existing jobs and removes any old pieces.
        """
        if cmds.scriptJob(exists=self.selection_job):
            cmds.scriptJob(kill=self.selection_job, force=True)
        if cmds.scriptJob(exists=self.validation_job):
            cmds.scriptJob(kill=self.validation_job, force=True)

        old_pieces = cmds.ls(f'{self.root_parent}*', dag=True, transforms=True)
        if old_pieces:
            cmds.delete(old_pieces)

        self.reset()

    def reset(self):
        """
        Resets the state of the Builder object.
        """
        self.__init__()
