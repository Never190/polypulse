import bpy
import gpu
import mathutils
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from gpu_extras.batch import batch_for_shader
from bpy.props import BoolProperty
from bpy.types import Operator, Panel
from .. import PolyPulseI18N
from .. import get_selected_mesh_objects, ensure_object_mode, show_popup
_overlay_handle = None
_overlay_enabled = False
_cached_shader = None
_geom_cache = None
_geom_cache_signature = None
COLOR_NGON = 1.0, 0.0, 0.0, 0.45
COLOR_MISSING_UV = 1.0, 0.9, 0.0, 0.45
COLOR_DUP_VERT = 0.2, 0.5, 1.0, 1.0
DUP_VERT_THRESHOLD = 0.0001
UV_AREA_EPSILON = 1e-08


def _get_uniform_color_shader():
    global _cached_shader
    if _cached_shader is not None:
        return _cached_shader
    shader_candidates = ('UNIFORM_COLOR', '3D_UNIFORM_COLOR',
        '2D_UNIFORM_COLOR', 'POLYLINE_UNIFORM_COLOR')
    for shader_name in shader_candidates:
        try:
            _cached_shader = gpu.shader.from_builtin(shader_name)
            return _cached_shader
        except (Exception,):
            continue
    return None


def _gpu_safe_blend_set(mode):
    try:
        gpu.state.blend_set(mode)
    except (AttributeError, TypeError):
        pass


def _gpu_safe_depth_test_set(mode):
    try:
        gpu.state.depth_test_set(mode)
    except (AttributeError, TypeError):
        pass


def _gpu_safe_depth_mask_set(value):
    try:
        gpu.state.depth_mask_set(value)
    except (AttributeError, TypeError):
        pass


def _gpu_safe_point_size_set(size):
    try:
        gpu.state.point_size_set(size)
    except (AttributeError, TypeError):
        try:
            import bgl
            bgl.glPointSize(size)
        except (ImportError, Exception):
            pass


def _is_poly_uv_missing(poly, uv_data):
    if uv_data is None:
        return True
    uv_coords = [uv_data[loop_idx].uv for loop_idx in poly.loop_indices]
    if not uv_coords:
        return True
    first = uv_coords[0]
    all_same = True
    for uv in uv_coords[1:]:
        if abs(uv.x - first.x) > 1e-06 or abs(uv.y - first.y) > 1e-06:
            all_same = False
            break
    if all_same:
        return True
    area = 0.0
    n = len(uv_coords)
    for i in range(n):
        x1, y1 = uv_coords[i].x, uv_coords[i].y
        x2, y2 = uv_coords[(i + 1) % n].x, uv_coords[(i + 1) % n].y
        area += x1 * y2 - x2 * y1
    area = abs(area) * 0.5
    if area < UV_AREA_EPSILON:
        return True
    return False


def _collect_geometry(selected):
    ngon_tris = []
    missing_uv_tris = []
    dup_vert_points = []
    ngon_count = 0
    missing_uv_count = 0
    dup_vert_count = 0
    for obj in selected:
        mesh = obj.data
        if not mesh.vertices or not mesh.polygons:
            continue
        matrix = obj.matrix_world
        world_verts = [(matrix @ v.co) for v in mesh.vertices]
        uv_layer = mesh.uv_layers.active
        uv_data = uv_layer.data if uv_layer is not None else None
        for poly in mesh.polygons:
            unique_vert_indices = list(set(poly.vertices))
            is_ngon = poly.loop_total > 4 and len(unique_vert_indices) > 4
            loop_start = poly.loop_start
            loop_total = poly.loop_total
            poly_verts = [world_verts[mesh.loops[loop_start + i].
                vertex_index] for i in range(loop_total)]
            if is_ngon:
                ngon_count += 1
                try:
                    tris = tessellate_polygon([poly_verts])
                    for tri in tris:
                        v0 = poly_verts[tri[0]]
                        v1 = poly_verts[tri[1]]
                        v2 = poly_verts[tri[2]]
                        ngon_tris.append((v0.x, v0.y, v0.z))
                        ngon_tris.append((v1.x, v1.y, v1.z))
                        ngon_tris.append((v2.x, v2.y, v2.z))
                except Exception:
                    v0 = poly_verts[0]
                    for i in range(1, len(poly_verts) - 1):
                        v1 = poly_verts[i]
                        v2 = poly_verts[i + 1]
                        ngon_tris.append((v0.x, v0.y, v0.z))
                        ngon_tris.append((v1.x, v1.y, v1.z))
                        ngon_tris.append((v2.x, v2.y, v2.z))
            elif _is_poly_uv_missing(poly, uv_data):
                missing_uv_count += 1
                n = len(poly_verts)
                if n == 3:
                    v0, v1, v2 = poly_verts
                    missing_uv_tris.append((v0.x, v0.y, v0.z))
                    missing_uv_tris.append((v1.x, v1.y, v1.z))
                    missing_uv_tris.append((v2.x, v2.y, v2.z))
                elif n == 4:
                    v0, v1, v2, v3 = poly_verts
                    missing_uv_tris.append((v0.x, v0.y, v0.z))
                    missing_uv_tris.append((v1.x, v1.y, v1.z))
                    missing_uv_tris.append((v2.x, v2.y, v2.z))
                    missing_uv_tris.append((v0.x, v0.y, v0.z))
                    missing_uv_tris.append((v2.x, v2.y, v2.z))
                    missing_uv_tris.append((v3.x, v3.y, v3.z))
                elif n > 4:
                    pass
        n_verts = len(world_verts)
        if n_verts > 1:
            kd = mathutils.kdtree.KDTree(n_verts)
            for i, v in enumerate(world_verts):
                kd.insert(v, i)
            kd.balance()
            dup_indices = set()
            for i, co in enumerate(world_verts):
                if len(kd.find_range(co, DUP_VERT_THRESHOLD)) > 1:
                    dup_indices.add(i)
            for idx in dup_indices:
                co = world_verts[idx]
                dup_vert_points.append((co.x, co.y, co.z))
            dup_vert_count += len(dup_indices)
    return (ngon_tris, missing_uv_tris, dup_vert_points, ngon_count,
        missing_uv_count, dup_vert_count)


def _get_selection_signature(selected):
    sig = []
    for obj in selected:
        mesh = obj.data
        sig.append((obj.name, len(mesh.vertices), len(mesh.polygons), tuple
            (round(x, 6) for row in obj.matrix_world for x in row)))
    return tuple(sig)


def _draw_overlay_callback():
    global _geom_cache, _geom_cache_signature
    if not _overlay_enabled:
        return
    context = bpy.context
    if context is None:
        return
    selected = [o for o in context.selected_objects if o.type == 'MESH']
    if not selected:
        return
    shader = _get_uniform_color_shader()
    if shader is None:
        return
    sig = _get_selection_signature(selected)
    if sig != _geom_cache_signature:
        _geom_cache = _collect_geometry(selected)
        _geom_cache_signature = sig
    ngon_tris, missing_uv_tris, dup_vert_points, _, _, _ = _geom_cache
    if not ngon_tris and not missing_uv_tris and not dup_vert_points:
        return
    _gpu_safe_blend_set('ALPHA')
    _gpu_safe_depth_test_set('LESS_EQUAL')
    _gpu_safe_depth_mask_set(False)
    if ngon_tris:
        try:
            shader.bind()
            shader.uniform_float('color', COLOR_NGON)
            batch = batch_for_shader(shader, 'TRIS', {'pos': ngon_tris})
            batch.draw(shader)
        except Exception:
            pass
    if missing_uv_tris:
        try:
            shader.bind()
            shader.uniform_float('color', COLOR_MISSING_UV)
            batch = batch_for_shader(shader, 'TRIS', {'pos': missing_uv_tris})
            batch.draw(shader)
        except Exception:
            pass
    if dup_vert_points:
        try:
            _gpu_safe_point_size_set(8.0)
            shader.bind()
            shader.uniform_float('color', COLOR_DUP_VERT)
            batch = batch_for_shader(shader, 'POINTS', {'pos': dup_vert_points}
                )
            batch.draw(shader)
        except Exception:
            pass
    _gpu_safe_depth_mask_set(True)
    _gpu_safe_depth_test_set('NONE')
    _gpu_safe_blend_set('NONE')


class POLYPULSE_OT_visual_scan(Operator):
    bl_idname = 'polypulse.visual_scan'
    bl_label = 'Visual Scan'
    bl_description = (
        'Toggle viewport overlay: red=ngons, yellow=missing UV, blue=dup verts'
        )
    bl_icon = 'VIEWZOOM'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        global _overlay_handle, _overlay_enabled, _geom_cache, _geom_cache_signature
        if _overlay_enabled:
            if _overlay_handle is not None:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(_overlay_handle,
                        'WINDOW')
                except Exception:
                    pass
                _overlay_handle = None
            _overlay_enabled = False
            _geom_cache = None
            _geom_cache_signature = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            self.report({'INFO'}, 'PolyPulse: Visual Scan OFF')
            context.scene.polypulse_props.last_operation = 'Visual Scan: OFF'
            return {'FINISHED'}
        _geom_cache = None
        _geom_cache_signature = None
        _overlay_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_overlay_callback, (), 'WINDOW', 'POST_VIEW')
        _overlay_enabled = True
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        selected = get_selected_mesh_objects(context)
        _, _, _, ngon_count, missing_uv_count, dup_vert_count = (
            _collect_geometry(selected))
        self.report({'INFO'},
            f'PolyPulse: Visual Scan ON — ngons={ngon_count}, missing_uv={missing_uv_count}, dup_verts={dup_vert_count}'
            )
        context.scene.polypulse_props.last_operation = (
            f'Visual Scan: ON (ngons={ngon_count}, missing_uv={missing_uv_count}, dup_verts={dup_vert_count})'
            )
        show_popup(context, title='PolyPulse: Visual Scan ON', icon=
            'VIEWZOOM', lines=['Overlay enabled in viewport!', '', (
            f'Ngons (red):         {ngon_count}', 'ERROR'), (
            f'Missing UV (yellow): {missing_uv_count}', 'INFO'), (
            f'Dup verts (blue):   {dup_vert_count}', 'VERTEXSEL'), '',
            'Click again to disable'])
        return {'FINISHED'}


class POLYPULSE_PT_asset_preparation(Panel):
    bl_label = 'Asset Preparation'
    bl_idname = 'POLYPULSE_PT_asset_preparation'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PolyPulse'
    bl_parent_id = 'POLYPULSE_PT_main'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props
        col = layout.column(align=True)
        col.label(text=PolyPulseI18N.t('section_collider'), icon='MESH_CUBE')
        box = col.box()
        row = box.row(align=True)
        row.scale_y = 1.05
        op = row.operator('polypulse.generate_collider', text='Box', icon=
            'MESH_CUBE')
        op.collider_type = 'BOX'
        op = row.operator('polypulse.generate_collider', text='Sphere',
            icon='MESH_UVSPHERE')
        op.collider_type = 'SPHERE'
        row2 = box.row(align=True)
        row2.scale_y = 1.05
        op = row2.operator('polypulse.generate_collider', text='Capsule',
            icon='MESH_CYLINDER')
        op.collider_type = 'CAPSULE'
        op = row2.operator('polypulse.generate_collider', text='Convex',
            icon='MESH_ICOSPHERE')
        op.collider_type = 'CONVEX'
        layout.separator()
        col = layout.column(align=True)
        col.label(text=PolyPulseI18N.t('section_uv_atlas'), icon=
            'MESH_UVSPHERE')
        box2 = col.box()
        col2 = box2.column(align=True)
        col2.scale_y = 1.05
        col2.operator('polypulse.create_uv_atlas', text=PolyPulseI18N.t(
            'btn_create_uv_atlas'), icon='MESH_UVSPHERE')
        layout.separator()
        col = layout.column(align=True)
        col.label(text=PolyPulseI18N.t('section_visual'), icon='VIEWZOOM')
        box3 = col.box()
        col3 = box3.column(align=True)
        col3.scale_y = 1.05
        col3.operator('polypulse.visual_scan', text=PolyPulseI18N.t(
            'btn_visual_scan'), icon='VIEWZOOM')
        legend = box3.column(align=True)
        legend.scale_y = 0.85
        legend.label(text=f"{PolyPulseI18N.t('lbl_legend')}:", icon='INFO')
        legend.label(text=f"{PolyPulseI18N.t('lbl_red_ngons')}", icon='ERROR')
        legend.label(text=f"{PolyPulseI18N.t('lbl_yellow_uv')}", icon='INFO')
        legend.label(text=f"{PolyPulseI18N.t('lbl_blue_dups')}", icon=
            'VERTEXSEL')


def cleanup_overlay():
    global _overlay_handle, _overlay_enabled, _geom_cache, _geom_cache_signature, _cached_shader
    if _overlay_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_overlay_handle, 'WINDOW'
                )
        except Exception:
            pass
        _overlay_handle = None
    _overlay_enabled = False
    _geom_cache = None
    _geom_cache_signature = None
    _cached_shader = None


classes = POLYPULSE_OT_visual_scan, POLYPULSE_PT_asset_preparation
