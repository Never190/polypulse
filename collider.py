import bpy
import time
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty, StringProperty
from bpy.types import Operator
from .. import PolyPulseI18N
from .. import get_selected_mesh_objects, ensure_object_mode, show_popup
MAX_OBJECTS = 128
MAX_POLYGONS = 100000


def _collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _safe_targets(objects):
    out, seen = [], set()
    for obj in objects:
        if obj.type != 'MESH' or not obj.data:
            continue
        ptr = obj.data.as_pointer()
        if ptr not in seen:
            seen.add(ptr)
            out.append(obj)
    return out


def _select_only(objects, active=None):
    for obj in bpy.context.view_layer.objects:
        try:
            obj.select_set(False)
        except ReferenceError:
            pass
    for obj in objects:
        obj.select_set(True)
    if active:
        bpy.context.view_layer.objects.active = active


def _make_target(source_objects, name):
    coll = _collection('PolyPulse_Bake_Work')
    copies = []
    for src in source_objects:
        dup = src.copy()
        dup.data = src.data.copy()
        dup.animation_data_clear()
        coll.objects.link(dup)
        copies.append(dup)
    _select_only(copies, copies[0])
    bpy.ops.object.join()
    target = bpy.context.object
    target.name = name
    target.data.name = name + '_Mesh'
    return target, coll


def _new_atlas_material(image, name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF') or nodes.new('ShaderNodeBsdfPrincipled'
        )
    tex = nodes.new('ShaderNodeTexImage')
    tex.name = 'PolyPulse_Baked_Atlas'
    tex.image = image
    tex.interpolation = 'Linear'
    links.new(tex.outputs.get('Color'), bsdf.inputs.get('Base Color'))
    return mat, tex


def _hide_sources(source_objects):
    backup = _collection('PolyPulse_Atlas_Source_Backup')
    for obj in source_objects:
        for coll in list(obj.users_collection):
            try:
                coll.objects.unlink(obj)
            except RuntimeError:
                pass
        backup.objects.link(obj)
        obj.hide_viewport = True
        obj.hide_render = True
    backup.hide_viewport = True
    backup.hide_render = True
    return backup


class POLYPULSE_OT_create_uv_atlas(Operator):
    bl_idname = 'polypulse.create_uv_atlas'
    bl_label = 'Bake Texture Atlas'
    bl_description = 'Create a real baked texture atlas from selected objects'
    bl_icon = 'IMAGE_DATA'
    bl_options = {'REGISTER', 'UNDO'}
    angle_limit: FloatProperty(name='Angle Limit', default=1.15192, min=0.0,
        max=3.14159, precision=5)
    island_margin: FloatProperty(name='Island Margin', default=0.02, min=
        0.0, max=0.5, precision=3)
    merge_materials: BoolProperty(name='Bake Atlas Material', default=True)
    atlas_size: IntProperty(name='Atlas Size', default=2048, min=256, max=
        8192, step=256)
    image_name: StringProperty(name='Image Name', default=
        'PolyPulse_BakedAtlas')
    bake_type: EnumProperty(name='Bake Type', items=[('DIFFUSE',
        'Diffuse Color', 'Bake base color without lighting'), ('EMIT',
        'Emission', 'Bake emitted shader color')], default='DIFFUSE')

    @classmethod
    def poll(cls, context):
        return bool(get_selected_mesh_objects(context))

    def execute(self, context):
        started = time.perf_counter()
        original_selection = list(context.selected_objects)
        original_active = context.view_layer.objects.active
        target = None
        work_coll = None
        backup = None
        try:
            ensure_object_mode(context)
            sources = _safe_targets(list(get_selected_mesh_objects(context)))
            total_polys = sum(len(o.data.polygons) for o in sources)
            if not sources:
                self.report({'WARNING'}, 'PolyPulse: no mesh objects selected')
                return {'CANCELLED'}
            if len(sources) > MAX_OBJECTS:
                self.report({'ERROR'},
                    f'PolyPulse: bake atlas cancelled safely: max {MAX_OBJECTS} unique meshes'
                    )
                return {'CANCELLED'}
            if total_polys > MAX_POLYGONS:
                self.report({'ERROR'},
                    f'PolyPulse: bake atlas cancelled safely above {MAX_POLYGONS:,} polygons'
                    )
                return {'CANCELLED'}
            if any(len(o.data.polygons) == 0 for o in sources):
                self.report({'ERROR'},
                    'PolyPulse: bake atlas cancelled: empty mesh selected')
                return {'CANCELLED'}
            estimated_islands = len(sources) * 4
            import math as _math
            ideal_atlas = max(256, int(2 ** _math.ceil(_math.log2(_math.
                sqrt(estimated_islands) * 64))))
            ideal_atlas = min(ideal_atlas, 8192)
            atlas_warning = None
            if self.atlas_size < ideal_atlas:
                atlas_warning = (
                    f"Atlas size {self.atlas_size}px is small for {len(sources)} objects (~{estimated_islands} UV islands). Recommended: {ideal_atlas}px to avoid blurry textures ('мыло')."
                    )
                print(f'PolyPulse [WARN] {atlas_warning}')
            target, work_coll = _make_target(sources, 'PolyPulse_BakedAtlas')
            _select_only([target], target)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=self.angle_limit,
                island_margin=self.island_margin)
            bpy.ops.uv.pack_islands(margin=self.island_margin, rotate=True)
            bpy.ops.object.mode_set(mode='OBJECT')
            image = bpy.data.images.get(self.image_name)
            if image:
                image.name = self.image_name + '_OLD'
            image = bpy.data.images.new(self.image_name, width=self.
                atlas_size, height=self.atlas_size, alpha=False)
            image.generated_color = 1.0, 0.0, 1.0, 1.0
            atlas_mat, image_node = _new_atlas_material(image,
                'PolyPulse_BakedAtlas_Material')
            target.data.materials.clear()
            target.data.materials.append(atlas_mat)
            src_hide_state = []
            for src in sources:
                src_hide_state.append((src, src.hide_viewport, src.hide_render)
                    )
                src.hide_viewport = False
                src.hide_render = False
            _select_only(sources + [target], target)
            nodes = target.data.materials[0].node_tree.nodes
            for node in nodes:
                node.select = False
            image_node.select = True
            nodes.active = image_node
            scene = context.scene
            old_engine = scene.render.engine
            old_samples = getattr(scene.cycles, 'samples', None) if hasattr(
                scene, 'cycles') else None
            try:
                scene.render.engine = 'CYCLES'
                if scene.render.engine != 'CYCLES':
                    raise RuntimeError(
                        f'Blender refused Cycles bake engine (current: {scene.render.engine})'
                        )
                bake_settings = scene.render.bake
                if hasattr(bake_settings, 'use_clear'):
                    bake_settings.use_clear = True
                if hasattr(bake_settings, 'margin'):
                    bake_settings.margin = max(1, int(self.island_margin *
                        self.atlas_size))
                if hasattr(bake_settings, 'target'):
                    bake_settings.target = 'IMAGE_TEXTURES'
                if hasattr(bake_settings, 'use_selected_to_active'):
                    bake_settings.use_selected_to_active = True
                if hasattr(bake_settings, 'max_ray_distance'):
                    bake_settings.max_ray_distance = 0.005
                if hasattr(scene, 'cycles'):
                    scene.cycles.samples = min(int(getattr(scene.cycles,
                        'samples', 32)), 32)
                if self.bake_type == 'DIFFUSE':
                    bpy.ops.object.bake(type='DIFFUSE', pass_filter={
                        'COLOR'}, use_selected_to_active=True, use_clear=
                        True, margin=max(1, int(self.island_margin * self.
                        atlas_size)))
                else:
                    bpy.ops.object.bake(type='EMIT', use_selected_to_active
                        =True, use_clear=True, margin=max(1, int(self.
                        island_margin * self.atlas_size)))
                image.update()
            finally:
                scene.render.engine = old_engine
                if old_samples is not None:
                    scene.cycles.samples = old_samples
                for src, hv, hr in src_hide_state:
                    try:
                        src.hide_viewport = hv
                        src.hide_render = hr
                    except ReferenceError:
                        pass
            backup = _hide_sources(sources)
            target.hide_viewport = False
            target.hide_render = False
            elapsed = time.perf_counter() - started
            props = scene.polypulse_props
            props.last_operation = (
                f'Texture Atlas baked: {len(sources)} objects, {total_polys:,} polygons, {self.atlas_size}px, {elapsed:.2f}s'
                )
            if hasattr(props, 'uv_atlas_seconds'):
                props.uv_atlas_seconds = elapsed
            if hasattr(props, 'uv_atlas_timing'):
                props.uv_atlas_timing = (
                    f'join+unwrap+bake: {elapsed * 1000:.1f} ms')
            self.report({'INFO'},
                f'PolyPulse: baked {self.atlas_size}px texture atlas in {elapsed:.2f}s'
                )
            popup_lines = [(f'Source objects: {len(sources)}',
                'OBJECT_DATA'), (f'Atlas object: {target.name}',
                'MESH_DATA'), (
                f'Atlas image: {image.name} ({self.atlas_size}px)',
                'IMAGE_DATA'), (f'Bake time: {elapsed:.2f}s', 'TIME'),
                'Originals moved to hidden backup collection']
            if atlas_warning:
                popup_lines.append('')
                popup_lines.append((f'⚠ {atlas_warning}', 'ERROR'))
                popup_lines.append((
                    'Re-bake with larger Atlas Size for sharper textures.',
                    'INFO'))
            show_popup(context, title='PolyPulse: Texture Atlas Baked',
                icon='IMAGE_DATA', lines=popup_lines)
            _select_only([target], target)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},
                f'PolyPulse: texture atlas bake cancelled safely: {exc}')
            target_name = getattr(target, 'name', None
                ) if target is not None else None
            if target_name and bpy.data.objects.get(target_name) is not None:
                bpy.data.objects.remove(bpy.data.objects.get(target_name),
                    do_unlink=True)
            return {'CANCELLED'}
        finally:
            try:
                if context.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            target_name = getattr(target, 'name', None
                ) if target is not None else None
            if target_name is None or bpy.data.objects.get(target_name
                ) is None:
                for obj in original_selection:
                    try:
                        obj.hide_viewport = False
                        obj.hide_render = False
                    except ReferenceError:
                        pass


classes = POLYPULSE_OT_create_uv_atlas,
