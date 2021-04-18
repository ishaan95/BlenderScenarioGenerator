# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
from mathutils import Vector, Matrix
from idprop.types import IDPropertyArray

from math import pi

from . import helpers


class DSC_OT_junction(bpy.types.Operator):
    bl_idname = 'dsc.junction'
    bl_label = 'Junction'
    bl_description = 'Create a junction'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def create_object_xodr(self, context, point_start, point_end, snapped_start):
        '''
            Create a junction object
        '''
        if point_end == point_start:
            self.report({"WARNING"}, "First and second selection are equal, "
                "direction can not be determined!")
            return None
        obj_id = helpers.get_new_id_opendrive(context)
        mesh = bpy.data.meshes.new('junction_' + str(obj_id))
        obj = bpy.data.objects.new(mesh.name, mesh)
        helpers.link_object_opendrive(context, obj)

        vertices = [(0.0, -4.0, 0.0),
                    (-4.0, -4.0, 0.0),
                    (-4.0, 0.0, 0.0),
                    (-4.0, 4.0, 0.0),
                    (0.0, 4.0, 0.0),
                    (4.0, 4.0, 0.0),
                    (4.0, 0.0, 0.0),
                    (4.0, -4.0, 0.0),
                    ]
        edges = [[0, 1],[1, 2],[2, 3],[3, 4],[4, 5],[5, 6],[6, 7],[7, 0]]
        faces = [[0, 1, 2, 3, 4, 5, 6, 7]]
        mesh.from_pydata(vertices, edges, faces)
        if snapped_start:
            # Use start point instead of center point as origin
            matrix = Matrix.Translation((0.0, 4.0, 0.0))
            obj.data.transform(matrix)

        helpers.select_activate_object(context, obj)

        # Rotate, translate, according to selected points
        vector_start_end_xy = (point_end - point_start).to_2d()
        vector_obj = obj.data.vertices[4].co - obj.data.vertices[0].co
        heading_start = vector_start_end_xy.angle_signed(vector_obj.to_2d())
        self.transform_object_wrt_start(obj, point_start, heading_start)

        # Remember connecting points for snapping
        obj['cp_down'] = obj.location + obj.data.vertices[0].co
        obj['cp_left'] = obj.location + obj.data.vertices[2].co
        obj['cp_up'] = obj.location + obj.data.vertices[4].co
        obj['cp_right'] = obj.location + obj.data.vertices[6].co

        # Set OpenDRIVE custom properties
        obj['id_xodr'] = obj_id
        obj['t_junction_e_junction_type'] = 'default'
        obj['t_junction_planView_geometry_x'] = point_start.x
        obj['t_junction_planView_geometry_y'] = point_start.y
        vector_hdg_down = obj.data.vertices[0].co - obj.data.vertices[4].co
        vector_hdg_left = obj.data.vertices[2].co - obj.data.vertices[6].co
        vector_hdg_up = obj.data.vertices[4].co - obj.data.vertices[0].co
        vector_hdg_right = obj.data.vertices[6].co - obj.data.vertices[2].co
        vec_0_1 = Vector((1.0, 0.0))
        obj['hdg_down'] = vector_hdg_down.to_2d().angle_signed(vec_0_1)
        obj['hdg_left'] = vector_hdg_left.to_2d().angle_signed(vec_0_1)
        obj['hdg_up'] = vector_hdg_up.to_2d().angle_signed(vec_0_1)
        obj['hdg_right'] = vector_hdg_right.to_2d().angle_signed(vec_0_1)

        obj['incoming_roads'] = {'cp_down': None, 'cp_left': None, 'cp_up': None, 'cp_right': None}

        return obj

    def create_stencil(self, context, point_start, heading_start, snapped_start):
        '''
            Create a stencil object with fake user or find older one in bpy data and
            relink to scene currently only support OBJECT mode.
        '''
        stencil = bpy.data.objects.get('dsc_stencil_object')
        if stencil is not None:
            if context.scene.objects.get('dsc_stencil_object') is None:
                context.scene.collection.objects.link(stencil)
        else:
            # Create object from mesh
            mesh = bpy.data.meshes.new("dsc_stencil_object")
            vertices = [(0.0, 0.0, 0.0),
                        (8.0, 0.0, 0.0),
                        (-4.0, -4.0, 0.0),
                        (-4.0, 4.0, 0.0),
                        (4.0, 4.0, 0.0),
                        (4.0, -4.0, 0.0),
                        ]
            edges = [[0, 1],[2, 3],[3, 4],[4, 5],[5, 2]]
            faces = []
            mesh.from_pydata(vertices, edges, faces)
            self.stencil = bpy.data.objects.new("dsc_stencil_object", mesh)
            if snapped_start:
                # Use start point instead of center point as origin
                matrix = Matrix.Translation((4.0, 0.0, 0.0))
                self.stencil.data.transform(matrix)
            self.transform_object_wrt_start(self.stencil, point_start, heading_start)
            # Link
            context.scene.collection.objects.link(self.stencil)
            self.stencil.use_fake_user = True
            self.stencil.data.use_fake_user = True

    def remove_stencil(self):
        '''
            Unlink stencil, needs to be in OBJECT mode.
        '''
        stencil = bpy.data.objects.get('dsc_stencil_object')
        if stencil is not None:
            bpy.data.objects.remove(stencil, do_unlink=True)

    def update_stencil(self, point_end, snapped_start):
        # Transform stencil object to follow the mouse pointer
        vector_obj = self.stencil.data.vertices[1].co - self.stencil.data.vertices[0].co
        self.transform_object_wrt_end(self.stencil, vector_obj, point_end, snapped_start)

    def transform_object_wrt_start(self, obj, point_start, heading_start):
        '''
            Rotate and translate origin to start point and rotate to start heading.
        '''
        obj.location = point_start
        mat_rotation = Matrix.Rotation(heading_start, 4, 'Z')
        obj.data.transform(mat_rotation)
        obj.data.update()

    def transform_object_wrt_end(self, obj, vector_obj, point_end, snapped_start):
        '''
            Transform object according to selected end point (keep start point fixed).
        '''
        vector_selected = point_end - obj.location
        # Make sure vectors are not 0 lenght to avoid division error
        if vector_selected.length > 0 and vector_obj.length > 0:
            # Apply transformation
            if snapped_start:
                return
            else:
                if vector_selected.angle(vector_obj)-pi > 0:
                    # Avoid numerical issues due to vectors directly facing each other
                    mat_rotation = Matrix.Rotation(pi, 4, 'Z')
                else:
                    mat_rotation = vector_obj.rotation_difference(vector_selected).to_matrix().to_4x4()
                obj.data.transform(mat_rotation)
                obj.data.update()

    def project_point_end(self, point_start, heading_start, point_selected):
        '''
            Project selected point to direction vector.
        '''
        vector_selected = point_selected - point_start
        if vector_selected.length > 0:
            vector_object = Vector((1.0, 0.0, 0.0))
            vector_object.rotate(Matrix.Rotation(heading_start, 4, 'Z'))
            return point_start + vector_selected.project(vector_object)
        else:
            return point_selected

    def modal(self, context, event):
        # Display help text
        if self.state == 'INIT':
            context.workspace.status_text_set("Place object by clicking, hold CTRL to snap to grid, "
                "press ESCAPE, RIGHTMOUSE to exit.")
            # Set custom cursor
            bpy.context.window.cursor_modal_set('CROSSHAIR')
            # Reset snapping
            self.snapped_start = False
            self.state = 'SELECT_START'
        if event.type in {'NONE', 'TIMER', 'TIMER_REPORT', 'EVT_TWEAK_L', 'WINDOW_DEACTIVATE'}:
            return {'PASS_THROUGH'}
        # Update on move
        if event.type == 'MOUSEMOVE':
            # Snap to existing objects if any, otherwise xy plane
            self.hit, self.id_xodr_hit, self.cp_type, point_selected, heading_selected = \
                helpers.raycast_mouse_to_object_else_xy(context, event)
            context.scene.cursor.location = point_selected
            # CTRL activates grid snapping if not snapped to object
            if event.ctrl and not self.hit:
                bpy.ops.view3d.snap_cursor_to_grid()
                point_selected = context.scene.cursor.location
            # Process and remember points according to modal state machine
            if self.state == 'SELECT_START':
                self.point_selected_start = point_selected.copy()
                self.heading_selected_start = heading_selected
                # Make sure end point and heading is set even if mouse is not moved
                self.point_selected_end = point_selected
                self.heading_selected_end = heading_selected
            if self.state == 'SELECT_END':
                # For snapped case use projected end point
                if self.snapped_start:
                    point_selected = self.project_point_end(
                        self.point_selected_start, self.heading_selected_start, point_selected)
                    context.scene.cursor.location = point_selected
                    self.update_stencil(point_selected, self.snapped_start)
                else:
                    self.update_stencil(point_selected, self.snapped_start)
                self.point_selected_end = point_selected
                self.heading_selected_end = heading_selected
        # Select start and end
        elif event.type == 'LEFTMOUSE':
            if event.value == 'RELEASE':
                if self.state == 'SELECT_START':
                    # Find clickpoint in 3D and create stencil mesh
                    self.snapped_start = self.hit
                    self.id_xodr_start = self.id_xodr_hit
                    self.cp_type_start = self.cp_type
                    self.create_stencil(context, context.scene.cursor.location,
                        self.heading_selected_start, self.snapped_start)
                    # Make stencil active object
                    helpers.select_activate_object(context, self.stencil)
                    self.state = 'SELECT_END'
                    return {'RUNNING_MODAL'}
                if self.state == 'SELECT_END':
                    snapped_end = self.hit
                    cp_type_end = self.cp_type
                    # Create the final object
                    obj = self.create_object_xodr(context, self.point_selected_start,
                        self.point_selected_end, self.snapped_start)
                    if self.snapped_start:
                        link_type = 'start'
                        helpers.create_object_xodr_links(context, obj, link_type, self.id_xodr_start, self.cp_type_start)
                    if snapped_end:
                        link_type = 'end'
                        helpers.create_object_xodr_links(context, obj, link_type, self.id_xodr_hit, cp_type_end)
                    # Remove stencil and go back to initial state to draw again
                    self.remove_stencil()
                    self.state = 'INIT'
                    return {'RUNNING_MODAL'}
        # Cancel
        elif event.type in {'ESC', 'RIGHTMOUSE'}:
            # Make sure stencil is removed
            self.remove_stencil()
            # Remove header text with 'None'
            context.workspace.status_text_set(None)
            # Set custom cursor
            bpy.context.window.cursor_modal_restore()
            # Make sure to exit edit mode
            if bpy.context.active_object:
                if bpy.context.active_object.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            self.state = 'INIT'
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.init_loc_x = context.region.x
        self.value = event.mouse_x
        # For operator state machine
        # possible states: {'INIT','SELECTE_BEGINNING', 'SELECT_END'}
        self.state = 'INIT'

        bpy.ops.object.select_all(action='DESELECT')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
