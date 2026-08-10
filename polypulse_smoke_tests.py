import bpy
import bmesh
import math
from mathutils import Vector
from bpy.props import EnumProperty, BoolProperty
from bpy.types import Operator
from .. import PolyPulseI18N
from .. import get_selected_mesh_objects, ensure_object_mode, show_popup


def _create_box_mesh(name, center, size):
    mesh = bpy.data.meshes.new(name + '_mesh')
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj.location = center
    obj.scale = size.x, size.y, size.z
    return obj


def _create_sphere_mesh(name, center, radius):
    mesh = bpy.data.meshes.new(name + '_mesh')
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=12, radius=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj.location = center
    obj.scale = radius, radius, radius
    return obj


def _create_cylinder_mesh(name, center, radius, depth):
    mesh = bpy.data.meshes.new(name + '_mesh')
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
        radius1=radius, radius2=radius, depth=depth)
    bm.to_mesh(mesh)
    bm.free()
    obj.location = center
    return obj


COLLIDER_TYPES = [('BOX', 'Box Collider', 'Bounding box collider'), (
    'SPHERE', 'Sphere Collider', 'Sphere around the object'), ('CAPSULE',
    'Capsule Collider', 'Cylinder + 2 hemispheres'), ('CONVEX',
    'Convex Collider', 'Convex hull (precise)')]


def _world_bbox(src_obj):
    mesh = src_obj.data
    if not mesh.vertices:
        return None, None
    world_coords = [(src_obj.matrix_world @ v.co) for v in mesh.vertices]
    min_x = min(c.x for c in world_coords)
    max_x = max(c.x for c in world_coords)
    min_y = min(c.y for c in world_coords)
    max_y = max(c.y for c in world_coords)
    min_z = min(c.z for c in world_coords)
    max_z = max(c.z for c in world_coords)
    center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z +
        max_z) / 2.0))
    size = Vector((max_x - min_x, max_y - min_y, max_z - min_z))
    return center, size


def _parent_keep_world(collider, src_obj):
    collider.parent = src_obj
    collider.matrix_parent_inverse = src_obj.matrix_world.inverted()


def _create_box_collider(src_obj, name):
    center, size = _world_bbox(src_obj)
    if center is None:
        return None
    collider = _create_box_mesh(name, center, size)
    _parent_keep_world(collider, src_obj)
    return collider


def _create_sphere_collider(src_obj, name):
    center, size = _world_bbox(src_obj)
    if center is None:
        return None
    mesh = src_obj.data
    max_dist = 0.0
    for v in mesh.vertices:
        world_co = src_obj.matrix_world @ v.co
        dist = (world_co - center).length
        if dist > max_dist:
            max_dist = dist
    if max_dist < 1e-06:
        max_dist = 0.1
    collider = _create_sphere_mesh(name, center, max_dist)
    _parent_keep_world(collider, src_obj)
    return collider


def _create_capsule_collider(src_obj, name):
    center, size = _world_bbox(src_obj)
    if center is None:
        return None
    radius = max(size.x, size.y) / 2.0
    if radius < 1e-06:
        radius = 0.1
    if size.z < 2.0 * radius:
        print(
            f"PolyPulse [INFO] Object '{src_obj.name}' is too flat (Z={size.z:.4f} < 2*radius={2.0 * radius:.4f}), auto-switching Capsule → Box collider"
            )
        return _create_box_collider(src_obj, name)
    cylinder_height = max(0.01, size.z - 2.0 * radius)
    collider = _create_cylinder_mesh(name, center, radius, cylinder_height)
    bm = bmesh.new()
    bevel_ok = False
    try:
        bm.from_mesh(collider.data)
        bm.edges.ensure_lookup_table()
        top_z = cylinder_height / 2.0
        bottom_z = -cylinder_height / 2.0
        cap_edges = []
        for edge in bm.edges:
            v1, v2 = edge.verts
            on_top = abs(v1.co.z - top_z) < 1e-06 and abs(v2.co.z - top_z
                ) < 1e-06
            on_bot = abs(v1.co.z - bottom_z) < 1e-06 and abs(v2.co.z - bottom_z
                ) < 1e-06
            if on_top or on_bot:
                cap_edges.append(edge)
        if cap_edges:
            try:
                bmesh.ops.bevel(bm, geom=cap_edges, offset=radius,
                    offset_type='OFFSET', segments=8, profile=0.5, affect=
                    'EDGES')
                bevel_ok = True
            except Exception as exc:
                print(f'PolyPulse [WARN] Capsule bevel failed: {exc}')
                bevel_ok = False
        if bevel_ok and len(bm.verts) < 96:
            print(
                f'PolyPulse [WARN] Capsule bevel produced too few vertices ({len(bm.verts)} < 96) — bevel failed silently, falling back to UV-sphere capsule'
                )
            bevel_ok = False
        if bevel_ok:
            bm.to_mesh(collider.data)
    finally:
        bm.free()
    collider.data.update()
    if not bevel_ok:
        print(
            f"PolyPulse [INFO] Capsule fallback to UV-sphere for '{src_obj.name}' (bevel failed)"
            )
        try:
            bpy.data.objects.remove(collider, do_unlink=True)
        except Exception:
            pass
        mesh = bpy.data.meshes.new(name + '_mesh')
        new_obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(new_obj)
        bm = bmesh.new()
        try:
            bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16,
                radius=1.0)
            bm.to_mesh(mesh)
        finally:
            bm.free()
        new_obj.location = center
        new_obj.scale = radius, radius, size.z / 2.0
        collider = new_obj
    _parent_keep_world(collider, src_obj)
    return collider


def _create_convex_collider(src_obj, name):
    mesh = src_obj.data
    if not mesh.vertices:
        return None
    new_mesh = mesh.copy()
    new_mesh.name = name + '_mesh'
    collider = src_obj.copy()
    collider.data = new_mesh
    collider.name = name
    for coll in src_obj.users_collection:
        coll.objects.link(collider)
        break
    else:
        bpy.context.collection.objects.link(collider)
    for mod in list(collider.modifiers):
        collider.modifiers.remove(mod)
    bm = bmesh.new()
    bm.from_mesh(collider.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    try:
        result = bmesh.ops.convex_hull(bm, input=bm.verts,
            use_existing_faces=False)
        geom_to_remove = result.get('geom_unused', []) + result.get(
            'geom_holes', [])
        if geom_to_remove:
            bmesh.ops.delete(bm, geom=geom_to_remove, context='VERTS')
    except Exception:
        pass
    bm.to_mesh(collider.data)
    bm.free()
    collider.data.update()
    _parent_keep_world(collider, src_obj)
    return collider


COLLIDER_FACTORIES = {'BOX': _create_box_collider, 'SPHERE':
    _create_sphere_collider, 'CAPSULE': _create_capsule_collider, 'CONVEX':
    _create_convex_collider}


class POLYPULSE_OT_generate_collider(Operator):
    bl_idname = 'polypulse.generate_collider'
    bl_label = 'Generate Collider'
    bl_description = 'Generate game-ready collider (Box/Sphere/Capsule/Convex)'
    bl_icon = 'MESH_CUBE'
    bl_options = {'REGISTER', 'UNDO'}
    collider_type: EnumProperty(name='Collider Type', description=
        'Type of collider to generate', items=COLLIDER_TYPES, default='BOX')
    visible: BoolProperty(name='Visible in Render', description=
        'If False, collider is viewport-only (no render)', default=False)

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}
        ensure_object_mode(context)
        factory = COLLIDER_FACTORIES.get(self.collider_type)
        if factory is None:
            self.report({'ERROR'}, 'PolyPulse: Unknown collider type')
            return {'CANCELLED'}
        created_count = 0
        failed_count = 0
        original_active = context.active_object
        for src_obj in selected:
            for o in context.selected_objects:
                o.select_set(False)
            src_obj.select_set(True)
            context.view_layer.objects.active = src_obj
            type_suffix = self.collider_type.capitalize()
            collider_name = f'{src_obj.name}_COLLISION_{type_suffix}'
            try:
                collider = factory(src_obj, collider_name)
                if collider is None:
                    failed_count += 1
                    continue
                if not self.visible:
                    collider.hide_render = True
                collider['polypulse_collider'] = self.collider_type
                collider['polypulse_source'] = src_obj.name
                created_count += 1
            except Exception as exc:
                self.report({'WARNING'},
                    f"PolyPulse: collider for '{src_obj.name}' failed: {exc}")
                failed_count += 1
        for o in context.selected_objects:
            o.select_set(False)
        for src in selected:
            src.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active
        props = context.scene.polypulse_props
        props.last_operation = (
            f'Generated {created_count} {self.collider_type} colliders ({failed_count} failed)'
            )
        self.report({'INFO'},
            f'PolyPulse: {created_count} {self.collider_type} colliders created'
            )
        popup_lines = [(f'Type: {self.collider_type}', 'MESH_CUBE'), (
            f'Created: {created_count}', 'CHECKMARK')]
        if failed_count > 0:
            popup_lines.append((f'Failed: {failed_count}', 'ERROR'))
        popup_lines.append('')
        popup_lines.append('Ready for UE5 / Unity / Godot!')
        show_popup(context, title='PolyPulse: Colliders Generated', icon=
            'MESH_CUBE', lines=popup_lines)
        return {'FINISHED'}


classes = POLYPULSE_OT_generate_collider,
