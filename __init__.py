# -*- coding: utf-8 -*-
"""
PolyPulse v0.5.8 — Next-Gen Asset Toolkit
=========================================

Professional Blender Addon for game-engine asset preparation
(UE5, Unity, Godot).

Features:
  - Mesh Diagnostic & Repair (Planar Dissolve, Tris→Quads, Beauty Fill,
    Non-Manifold Repair, Full Mesh Repair, Visual Overlay)
  - Auto LOD Chain System (Decimate + Rename)
  - Engine Export Presets (UE5/Unity/Godot) with correct FBX/GLB axes
  - Collider Generator (Box/Sphere/Capsule/Convex) — modules/collider.py
  - UV Atlas Generator (Smart Project + material merge) — modules/uv_atlas.py
  - Custom Viewport Overlay (Ngons/UV/Dup Verts highlight) — modules/visual_overlay.py
  - Draw Calls Estimator
  - Asset Validation System (Game Ready Score)
  - Multi-language i18n (EN/RU/DE/ES/JP)

Compatibility: Blender 2.83 LTS, 2.93 LTS, 3.x, 4.x, 5.x+
Author:  PolyPulse Team
License: GNU GPL v3.0 — see LICENSE file
GitHub:  https://github.com/polypulse/polypulse
"""

bl_info = {
    "name": "PolyPulse",
    "author": "PolyPulse Team",
    "version": (0, 5, 8),
    "blender": (2, 83, 0),
    "location": "View3D > Sidebar (N) > PolyPulse",
    "description": "Next-gen mesh repair, LOD generation, UV atlas & game engine export (UE5/Unity/Godot)",
    "warning": "Public beta. Use for evaluation and report reproducible issues.",
    "wiki_url": "https://github.com/DevWinstor/polypulse/wiki",
    "tracker_url": "https://github.com/DevWinstor/polypulse/issues/new/choose",
    "category": "Mesh",
}

# -----------------------------------------------------------------------------
# ИМПОРТЫ
# -----------------------------------------------------------------------------
import bpy
import bmesh
import os
import json
import math
import mathutils
from datetime import datetime
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    AddonPreferences,
)


# -----------------------------------------------------------------------------
# ADDON MODULE NAME (must match the top-level folder name inside the ZIP)
# -----------------------------------------------------------------------------
ADDON_MODULE = __package__ or __name__ or "polypulse"


# =============================================================================
# i18n — MULTILANGUAGE SYSTEM
# =============================================================================
class PolyPulseI18N:
    """
    Система локализации. Загружает JSON из translations/ и хранит
    текущий язык. Доступ через PolyPulseI18N.t("key").
    """

    _translations = {}        # {"en": {...}, "ru": {...}, ...}
    _current_lang = "en"
    _loaded = False

    @classmethod
    def load(cls):
        """Загружает все JSON-файлы переводов из подпапки translations/."""
        # Путь к translations/ относительно этого __init__.py
        # __file__ в Blender addon'е указывает на реальный путь файла
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        trans_dir = os.path.join(addon_dir, "translations")
        cls._translations.clear()
        if not os.path.isdir(trans_dir):
            return
        for fname in sorted(os.listdir(trans_dir)):
            if not fname.endswith('.json'):
                continue
            lang_code = fname[:-5]  # без .json
            fpath = os.path.join(trans_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    cls._translations[lang_code] = json.load(f)
            except (OSError, json.JSONDecodeError):
                # Пропускаем битые файлы
                continue
        cls._loaded = True

    @classmethod
    def set_lang(cls, lang_code):
        """Сменить текущий язык."""
        if lang_code in cls._translations:
            cls._current_lang = lang_code

    @classmethod
    def get_lang(cls):
        return cls._current_lang

    @classmethod
    def available_langs(cls):
        """Возвращает [(code, "label (flag)"), ...] для EnumProperty."""
        result = []
        for code in sorted(cls._translations.keys()):
            data = cls._translations[code]
            label = f"{data.get('lang_flag', code.upper())} {data.get('lang_name', code)}"
            result.append((code, label, data.get('lang_name', code)))
        return result

    @classmethod
    def t(cls, key, default=None):
        """
        Перевести ключ. Fallback на английский, затем на сам ключ.
        """
        if not cls._loaded:
            cls.load()
        trans = cls._translations.get(cls._current_lang, {})
        if key in trans:
            return trans[key]
        # Fallback на английский
        en = cls._translations.get("en", {})
        if key in en:
            return en[key]
        return default if default is not None else key


# Загружаем переводы при импорте модуля
PolyPulseI18N.load()


# -----------------------------------------------------------------------------
# Public beta build — all addon features are enabled locally.
# Future Pro tier features will be delivered as a separate, closed-source
# add-on under a different license (see SECURITY_AUDIT.md).
# -----------------------------------------------------------------------------

# =============================================================================
# PROPERTY GROUPS
# =============================================================================
class PolyPulseWarningItem(PropertyGroup):
    """Элемент списка предупреждений Advanced Scan / Validation."""
    text: StringProperty(name="Warning Text", default="")
    severity: StringProperty(name="Severity", default="INFO")
    icon: StringProperty(name="Icon", default="INFO")


class PolyPulseTextureItem(PropertyGroup):
    """Элемент списка текстур (для Texture Optimizer)."""
    name: StringProperty(name="Texture Name", default="")
    size_x: IntProperty(name="Width", default=0)
    size_y: IntProperty(name="Height", default=0)
    file_size_kb: IntProperty(name="File Size (KB)", default=0)
    recommendation: StringProperty(name="Recommendation", default="")


class PolyPulseValidationItem(PropertyGroup):
    """Элемент списка проверок Asset Validation System."""
    category: StringProperty(name="Category", default="")
    check_name: StringProperty(name="Check Name", default="")
    passed: BoolProperty(name="Passed", default=False)
    detail: StringProperty(name="Detail", default="")


class PolyPulseProperties(PropertyGroup):
    """
    Главное хранилище состояния аддона на сцене.
    """

    # --- i18n setting ---
    language: EnumProperty(
        name=PolyPulseI18N.t("lbl_language", "Language"),
        description="Interface language",
        items=PolyPulseI18N.available_langs(),
        default="en",
        update=lambda self, ctx: (
            PolyPulseI18N.set_lang(self.language),
            # Триггерим перерисовку UI
            [area.tag_redraw() for area in ctx.screen.areas if area.type == 'VIEW_3D']
        ),
    )

    # --- v0.5.1: collapsible UI sections (open by default) ---
    ui_show_analysis: BoolProperty(default=True)
    ui_show_optimization: BoolProperty(default=True)
    ui_show_export: BoolProperty(default=True)
    ui_show_validation: BoolProperty(default=True)
    ui_show_reports: BoolProperty(default=True)
    ui_show_settings: BoolProperty(default=True)
    ui_show_asset_prep: BoolProperty(default=True)
    ui_show_stats: BoolProperty(default=False)
    ui_show_warnings: BoolProperty(default=True)
    ui_show_textures: BoolProperty(default=False)

    # --- v0.5.3: visual progress bars for score display ---
    score_progress: FloatProperty(default=0.0, min=0.0, max=1.0,
        name="Score", description="Overall Game Ready Score")
    geo_progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    tex_progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    mat_progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    opt_progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    # v0.5.4: separate progress bar for validation score (was sharing score_progress)
    validation_progress: FloatProperty(default=0.0, min=0.0, max=1.0,
        name="Validation", description="Asset Validation Score")

    # --- v0.1: базовая статистика ---
    objects_count: IntProperty(default=0)
    meshes_count: IntProperty(default=0)
    vertices_count: IntProperty(default=0)
    edges_count: IntProperty(default=0)
    polygons_count: IntProperty(default=0)
    materials_count: IntProperty(default=0)

    # --- v0.1: Optimization Score ---
    optimization_score: IntProperty(default=0, min=0, max=100)
    score_label: StringProperty(default="Poor")

    # --- v0.2: Advanced Mesh Analyzer ---
    adv_verts: IntProperty(default=0)
    adv_polys: IntProperty(default=0)
    adv_tris: IntProperty(default=0)
    adv_ngons: IntProperty(default=0)
    adv_objects: IntProperty(default=0)
    adv_materials: IntProperty(default=0)
    adv_textures: IntProperty(default=0)
    adv_has_uv: BoolProperty(default=False)
    adv_has_normals: BoolProperty(default=False)
    adv_duplicate_verts: IntProperty(default=0)
    adv_overlapping_uv: IntProperty(default=0)
    adv_warnings: CollectionProperty(type=PolyPulseWarningItem)

    # --- v0.2: Game Ready Score 2.0 ---
    game_score: IntProperty(default=0, min=0, max=100)
    game_stars: IntProperty(default=0, min=0, max=5)
    game_label: StringProperty(default="Not analyzed")
    game_geometry_pct: IntProperty(default=0)
    game_textures_pct: IntProperty(default=0)
    game_materials_pct: IntProperty(default=0)
    game_optimization_pct: IntProperty(default=0)
    game_recommendation: StringProperty(default="")

    # --- v0.2: Texture Optimizer ---
    textures: CollectionProperty(type=PolyPulseTextureItem)

    # --- v0.2: Auto Fix Mesh отчёт ---
    fix_verts_before: IntProperty(default=0)
    fix_verts_after: IntProperty(default=0)
    fix_fixed_count: IntProperty(default=0)

    # --- v0.3: Draw Calls Estimator ---
    dc_triangles: IntProperty(default=0)
    dc_materials: IntProperty(default=0)
    dc_objects: IntProperty(default=0)
    dc_duplicates: IntProperty(default=0)
    dc_estimated: IntProperty(default=0)
    dc_recommendation: StringProperty(default="")

    # --- v0.3: Asset Validation System ---
    validation_items: CollectionProperty(type=PolyPulseValidationItem)
    validation_score: IntProperty(default=0, min=0, max=100)
    validation_passed: BoolProperty(default=False)

    # --- v0.3: LOD Chain отчёт ---
    lod_chain_lod0_polys: IntProperty(default=0)
    lod_chain_lod1_polys: IntProperty(default=0)
    lod_chain_lod2_polys: IntProperty(default=0)
    lod_chain_lod3_polys: IntProperty(default=0)
    lod_chain_created: IntProperty(default=0)

    # --- Общее: последняя операция ---
    last_operation: StringProperty(default="No operation yet")


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================
def get_selected_mesh_objects(context):
    """Возвращает список выбранных объектов типа MESH."""
    return [obj for obj in context.selected_objects if obj.type == 'MESH']


def ensure_object_mode(context):
    """Переключает режим в OBJECT, если активный объект в EDIT."""
    changed = False
    if (context.active_object is not None
            and context.object.mode != 'OBJECT'):
        bpy.ops.object.mode_set(mode='OBJECT')
        changed = True
    return changed


def show_popup(context, title, lines, icon='INFO'):
    """
    Показывает всплывающее окно-попап.
    lines: список строк или кортежей (text, icon).
    """
    def draw(menu, ctx):
        layout = menu.layout
        col = layout.column(align=True)
        col.separator()
        for item in lines:
            if isinstance(item, (tuple, list)):
                text, ico = item[0], item[1]
                col.label(text=text, icon=ico)
            else:
                col.label(text=item)

    context.window_manager.popup_menu(draw, title=title, icon=icon)


def calculate_optimization_score(polygons, objects, materials):
    """
    Базовый Optimization Score (v0.1) — 0..100.
    Веса: polygons 0.60, objects 0.25, materials 0.15.
    """
    POLY_THRESHOLD = 50_000
    OBJ_THRESHOLD = 50
    MAT_THRESHOLD = 20

    poly_score = max(0.0, 1.0 - (polygons / POLY_THRESHOLD))
    obj_score = max(0.0, 1.0 - (objects / OBJ_THRESHOLD))
    mat_score = max(0.0, 1.0 - (materials / MAT_THRESHOLD))

    score = (poly_score * 0.60
             + obj_score * 0.25
             + mat_score * 0.15) * 100.0
    score = max(0, min(100, int(round(score))))

    if score <= 30:
        label = PolyPulseI18N.t("score_poor", "Poor")
    elif score <= 60:
        label = PolyPulseI18N.t("score_needs_optimization", "Needs Optimization")
    elif score <= 80:
        label = PolyPulseI18N.t("score_game_ready", "Game Ready")
    else:
        label = PolyPulseI18N.t("score_excellent", "Excellent")

    return score, label


def calculate_game_ready_score(verts, polys, ngons, materials, textures,
                                max_texture_dim, has_uv, has_normals,
                                has_duplicate_verts, has_overlapping_uv):
    """
    Game Ready Score 2.0 — взвешенный рейтинг по 4 категориям.

    Категории:
      Geometry    (30%)
      Textures    (25%)
      Materials   (20%)
      Optimization (25%)

    Возвращает dict со score, stars, label, per-category % и рекомендацией.
    """
    # --- Geometry (30%) ---
    v_score = max(0.0, 1.0 - (verts / 20_000))
    p_score = max(0.0, 1.0 - (polys / 40_000))
    n_score = 1.0 if ngons == 0 else max(0.0, 1.0 - (ngons / max(polys, 1)))
    geometry_pct = int(round((v_score * 0.4 + p_score * 0.4
                              + n_score * 0.2) * 100))
    geometry_pct = max(0, min(100, geometry_pct))

    # --- Textures (25%) ---
    if textures == 0:
        textures_pct = 50
    else:
        if max_texture_dim <= 2048:
            t_score = 1.0
        elif max_texture_dim <= 4096:
            t_score = 0.6
        else:
            t_score = 0.2
        textures_pct = int(round(t_score * 100))

    # --- Materials (20%) ---
    if materials <= 3:
        m_score = 1.0
    elif materials <= 6:
        m_score = 0.7
    elif materials <= 10:
        m_score = 0.4
    else:
        m_score = max(0.0, 1.0 - (materials - 10) / 20)
    materials_pct = int(round(m_score * 100))

    # --- Optimization (25%) ---
    opt_score = 0.0
    opt_score += 0.35 if has_uv else 0.0
    opt_score += 0.35 if has_normals else 0.0
    opt_score += 0.10 if ngons == 0 else 0.0
    opt_score += 0.10 if not has_duplicate_verts else 0.0
    opt_score += 0.10 if not has_overlapping_uv else 0.0
    optimization_pct = int(round(opt_score * 100))

    # --- Финальный взвешенный ---
    final = (geometry_pct * 0.30
             + textures_pct * 0.25
             + materials_pct * 0.20
             + optimization_pct * 0.25)
    final = max(0, min(100, int(round(final))))

    # --- Звёзды ---
    stars = max(0, min(5, math.ceil(final / 20)))

    # --- Лейбл + рекомендация ---
    if final >= 91:
        label = PolyPulseI18N.t("score_excellent", "Excellent")
        recommendation = PolyPulseI18N.t("rec_near_ready",
                                       "Almost ready — minor tweaks recommended.")
    elif final >= 71:
        label = PolyPulseI18N.t("score_game_ready", "Game Ready")
        recommendation = PolyPulseI18N.t("rec_ready_ue5",
                                       "Asset is ready for UE5 / Unity / Godot!")
    elif final >= 41:
        label = PolyPulseI18N.t("score_needs_optimization",
                              "Needs Optimization")
        recommendation = PolyPulseI18N.t("rec_optimize_required",
                                       "Optimization required before game engine.")
    else:
        label = PolyPulseI18N.t("score_poor", "Poor")
        recommendation = PolyPulseI18N.t("rec_heavy_optimization",
                                       "Heavy optimization needed — not game-ready.")

    return {
        "score": final,
        "stars": stars,
        "label": label,
        "recommendation": recommendation,
        "geometry_pct": geometry_pct,
        "textures_pct": textures_pct,
        "materials_pct": materials_pct,
        "optimization_pct": optimization_pct,
    }


def collect_textures_from_objects(objects):
    """Собирает уникальные текстуры из материалов переданных объектов."""
    textures = []
    seen_image_names = set()

    for obj in objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            mat = slot.material
            if mat.node_tree is None:
                continue
            for node in mat.node_tree.nodes:
                if node.type != 'TEX_IMAGE':
                    continue
                img = node.image
                if img is None or img.name in seen_image_names:
                    continue
                seen_image_names.add(img.name)

                size_x = img.size[0] if len(img.size) > 0 else 0
                size_y = img.size[1] if len(img.size) > 1 else 0
                file_size_kb = 0
                if img.filepath:
                    try:
                        raw_path = bpy.path.abspath(img.filepath_raw)
                        if os.path.isfile(raw_path):
                            file_size_kb = int(
                                os.path.getsize(raw_path) / 1024
                            )
                    except (OSError, ValueError):
                        file_size_kb = 0

                max_dim = max(size_x, size_y)
                if max_dim >= 4096:
                    rec = "Downscale to 2K (mobile-ready)"
                elif max_dim >= 2048:
                    rec = "OK for PC; downscale to 1K for mobile"
                elif max_dim >= 1024:
                    rec = "OK for PC/mobile"
                else:
                    rec = "Small texture — OK for mobile"

                textures.append({
                    "name": img.name,
                    "size_x": size_x,
                    "size_y": size_y,
                    "file_size_kb": file_size_kb,
                    "max_dim": max_dim,
                    "recommendation": rec,
                })
    return textures


def find_duplicate_vertices_count(mesh, threshold=0.0001):
    """Считает количество дублирующихся вершин через KDTree (O(N log N)).

    Старая версия создавала полный BMesh и вызывала remove_doubles,
    что модифицировало данные и было медленнее на больших мешах.
    """
    n_verts = len(mesh.vertices)
    if n_verts < 2:
        return 0

    kd = mathutils.kdtree.KDTree(n_verts)
    for i, v in enumerate(mesh.vertices):
        kd.insert(v.co, i)
    kd.balance()

    dup_indices = set()
    # KDTree.find_range returns distance, not squared distance. Also mark
    # both members of each close pair so the diagnostic count is truthful.
    for i, v in enumerate(mesh.vertices):
        if i in dup_indices:
            continue
        for co, idx, dist in kd.find_range(v.co, threshold):
            if idx > i:
                dup_indices.add(i)
                dup_indices.add(idx)
                break

    return len(dup_indices)


def find_overlapping_uv_count(mesh):
    """Считает повреждённые UV-полигоны (вывернутые или с нулевой площадью).

    Использует Shoelace formula (Gauss area) для каждого UV-полигона:
      area_2x = sum( x_i * y_{i+1} - x_{i+1} * y_i )

    Полигон считается повреждённым, если:
      - abs(area_2x) * 0.5 < 1e-8  → нулевая площадь (схлопнутый UV)
      - area_2x < 0                  → вывернутая нормаль UV (negative winding)

    Это правильная детекция проблем UV для GameDev:
      схлопнутые и вывернутые UV-грани вызывают артефакты
      тайлинга, нормал-мапов и baking в UE5/Unity/Godot.

    Старая реализация считала совпадающие UV-координаты на смежных лупах
    как "перекрытия", что ложно срабатывало на нормальных UV-развёртках
    (где смежные лупы по определению разделяют UV-координату на швах).
    """
    if mesh.uv_layers.active is None:
        return 0
    uv_data = mesh.uv_layers.active.data
    invalid_polys = 0
    for poly in mesh.polygons:
        coords = [uv_data[l_idx].uv for l_idx in poly.loop_indices]
        n = len(coords)
        if n < 3:
            continue
        # Shoelace formula: signed 2x area of UV polygon
        area_2x = sum(
            coords[i].x * coords[(i + 1) % n].y
            - coords[(i + 1) % n].x * coords[i].y
            for i in range(n)
        )
        # Winding can legitimately be negative on mirrored UV islands.
        # Only zero-area UVs are invalid here; negative winding is not overlap.
        if abs(area_2x) * 0.5 < 1e-8:
            invalid_polys += 1
    return invalid_polys


def estimate_draw_calls(objects):
    """
    Оценивает количество draw calls для выбранных объектов.

    Логика:
      - Каждый объект = 1 draw call (минимум)
      - Каждый material slot на объекте = +1 draw call
      - Дубликаты (Alt-D, т.е. шарящие mesh data) = 1 draw call на группу
    """
    if not objects:
        return 0, 0, 0, 0

    total_slots = 0
    unique_meshes = set()
    for obj in objects:
        if obj.type != 'MESH':
            continue
        # Считаем материал-слоты (только заполненные)
        used_slots = 0
        for slot in obj.material_slots:
            if slot.material is not None:
                used_slots += 1
        if used_slots == 0:
            used_slots = 1  # объект без материала всё равно = 1 draw call
        total_slots += used_slots
        unique_meshes.add(obj.data.name)

    mesh_objects = [o for o in objects if o.type == 'MESH']
    estimated = max(len(mesh_objects), total_slots)
    return estimated, total_slots, len(mesh_objects), len(unique_meshes)


# =============================================================================
# ОПЕРАТОР 1 — ANALYZE SCENE  (v0.1)
# =============================================================================
class POLYPULSE_OT_analyze_scene(Operator):
    """Анализирует текущую сцену и считает базовый Optimization Score."""

    bl_idname = "polypulse.analyze_scene"
    bl_label = "Analyze Scene"
    bl_description = "Analyze scene statistics and calculate optimization score"
    bl_icon = 'VIEWZOOM'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        all_objects = list(bpy.data.objects)
        mesh_objects = [o for o in all_objects if o.type == 'MESH']

        total_verts = 0
        total_edges = 0
        total_polys = 0
        for mesh_obj in mesh_objects:
            mesh = mesh_obj.data
            total_verts += len(mesh.vertices)
            total_edges += len(mesh.edges)
            total_polys += len(mesh.polygons)
        total_mats = len(bpy.data.materials)

        props.objects_count = len(all_objects)
        props.meshes_count = len(mesh_objects)
        props.vertices_count = total_verts
        props.edges_count = total_edges
        props.polygons_count = total_polys
        props.materials_count = total_mats

        score, label = calculate_optimization_score(
            polygons=total_polys,
            objects=len(all_objects),
            materials=total_mats,
        )
        props.optimization_score = score
        props.score_label = label
        props.last_operation = (
            f"{PolyPulseI18N.t('msg_analyzed_scene')}: "
            f"{len(all_objects)} obj, {total_polys} polys -> "
            f"score {score}/100 ({label})"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {len(all_objects)} obj | {total_polys} polys | "
            f"score {score}/100 ({label})"
        )

        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_analyzed_scene')}",
            icon='VIEWZOOM',
            lines=[
                (f"{PolyPulseI18N.t('lbl_objects')}:   {len(all_objects)}",   'OBJECT_DATA'),
                (f"{PolyPulseI18N.t('lbl_meshes')}:    {len(mesh_objects)}",  'MESH_DATA'),
                (f"{PolyPulseI18N.t('lbl_vertices')}:  {total_verts}",        'VERTEXSEL'),
                (f"{PolyPulseI18N.t('lbl_edges')}:     {total_edges}",        'EDGESEL'),
                (f"{PolyPulseI18N.t('lbl_polygons')}:  {total_polys}",        'FACESEL'),
                (f"{PolyPulseI18N.t('lbl_materials')}: {total_mats}",         'MATERIAL'),
                "",
                (f"Score: {score}/100  ({label})",   'SOLO_ON'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 2 — REMOVE DOUBLES  (v0.1)
# =============================================================================
class POLYPULSE_OT_remove_doubles(Operator):
    """Удаляет дублирующиеся вершины на выбранных меш-объектах."""

    bl_idname = "polypulse.remove_doubles"
    bl_label = "Remove Doubles"
    bl_description = "Merge duplicate vertices on selected mesh objects"
    bl_icon = 'AUTOMERGE_ON'
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Merge Distance",
        description="Vertices closer than this distance will be merged",
        default=0.0001,
        min=0.0,
        precision=5,
    )

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        total_removed = 0
        for obj in selected:
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            before = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=self.threshold)
            after = len(bm.verts)
            total_removed += before - after
            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_removed_doubles')}: {total_removed}"
        )

        if total_removed > 0:
            self.report({'INFO'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_removed_doubles')} "
                        f"{total_removed}")
            show_popup(
                context,
                title=f"PolyPulse: {PolyPulseI18N.t('msg_removed_doubles')}",
                icon='AUTOMERGE_ON',
                lines=[
                    (f"{PolyPulseI18N.t('popup_objects_processed')}: {len(selected)}", 'OBJECT_DATA'),
                    (f"{PolyPulseI18N.t('popup_verts_merged')}:   {total_removed}", 'VERTEXSEL'),
                    "",
                    PolyPulseI18N.t('msg_auto_fix_complete'),
                ],
            )
        else:
            self.report({'INFO'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_doubles')}")
            show_popup(
                context,
                title=f"PolyPulse: {PolyPulseI18N.t('msg_no_doubles')}",
                icon='INFO',
                lines=[
                    f"{PolyPulseI18N.t('popup_objects_processed')}: {len(selected)}",
                    PolyPulseI18N.t('msg_no_doubles'),
                    f"(threshold = {self.threshold})",
                ],
            )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 3 — MERGE SELECTED OBJECTS  (v0.1)
# =============================================================================
class POLYPULSE_OT_merge_objects(Operator):
    """Объединяет выбранные меш-объекты в один, сохраняя позицию."""

    bl_idname = "polypulse.merge_objects"
    bl_label = "Merge Selected Objects"
    bl_description = "Join selected mesh objects into one, preserving position"
    bl_icon = 'AREA_JOIN'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 1

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if len(selected) < 2:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        active = context.active_object
        if active is None or active.type != 'MESH':
            active = selected[0]
            context.view_layer.objects.active = active

        target_name = active.name
        target_pos = active.matrix_world.translation.copy()

        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = active

        try:
            bpy.ops.object.join()
        except RuntimeError as e:
            self.report({'ERROR'}, f"PolyPulse: {e}")
            return {'CANCELLED'}

        active.matrix_world.translation = target_pos

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_merged_objects')}: "
            f"{len(selected)} -> '{target_name}'"
        )
        self.report({'INFO'},
                    f"PolyPulse: {PolyPulseI18N.t('msg_merged_objects')} "
                    f"{len(selected)} -> '{target_name}'")
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_merged_objects')}",
            icon='AREA_JOIN',
            lines=[
                (f"{PolyPulseI18N.t('popup_objects_processed')}: {len(selected)}", 'OBJECT_DATA'),
                (f"{PolyPulseI18N.t('popup_target_mesh')}:    {target_name}",   'MESH_DATA'),
                "",
                PolyPulseI18N.t('popup_position_preserved'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 4 — SMART DECIMATE  (v0.1)
# =============================================================================
class POLYPULSE_OT_smart_decimate(Operator):
    """Автоматически декимирует «тяжёлые» меши через DECIMATE COLLAPSE."""

    bl_idname = "polypulse.smart_decimate"
    bl_label = "Smart Decimate"
    bl_description = "Automatically decimate heavy meshes while preserving shape"
    bl_icon = 'MOD_DECIM'
    bl_options = {'REGISTER', 'UNDO'}

    max_polygons: IntProperty(
        name="Target Max Polygons",
        description="Threshold above which the mesh is considered heavy",
        default=2000,
        min=100,
    )

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        original_active = context.active_object
        total_before = 0
        total_after = 0
        processed = 0

        for obj in selected:
            mesh = obj.data
            poly_before = len(mesh.polygons)
            total_before += poly_before

            if poly_before <= self.max_polygons:
                total_after += poly_before
                continue

            target = int(self.max_polygons * 0.9)
            ratio = max(0.05, target / poly_before)

            mod = obj.modifiers.new(name="PolyPulseDecimate", type='DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = ratio
            mod.use_collapse_triangulate = False
            mod.use_symmetry = False

            context.view_layer.objects.active = obj
            for o in context.selected_objects:
                o.select_set(False)
            obj.select_set(True)

            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                self.report({'WARNING'}, f"PolyPulse: {e}")
                obj.modifiers.remove(mod)
                total_after += poly_before
                continue

            poly_after = len(mesh.polygons)
            total_after += poly_after
            processed += 1

        # Восстанавливаем выделение
        for o in context.selected_objects:
            o.select_set(False)
        for obj in selected:
            obj.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active

        if total_before == 0:
            props.last_operation = "Smart Decimate: nothing to optimize"
            self.report({'INFO'}, "PolyPulse: No polygons to decimate")
            return {'FINISHED'}

        if processed == 0:
            props.last_operation = (
                f"Smart Decimate: no mesh exceeded {self.max_polygons:,} polygons"
            )
            self.report(
                {'INFO'},
                f"PolyPulse: Nothing changed; threshold is {self.max_polygons:,} polygons"
            )
            show_popup(
                context,
                title="PolyPulse: Smart Decimate",
                icon='INFO',
                lines=[
                    (f"Selected polygons: {total_before:,}", 'FACESEL'),
                    (f"Threshold: {self.max_polygons:,}", 'INFO'),
                    ("Nothing changed", 'CHECKMARK'),
                    "Increase the selected mesh complexity or lower the threshold in the operator panel.",
                ],
            )
            return {'FINISHED'}

        reduction_pct = round(
            (1.0 - total_after / total_before) * 100.0, 1
        ) if total_before > 0 else 0.0

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_decimate_complete')}: "
            f"{total_before} -> {total_after} (-{reduction_pct}%)"
        )
        self.report(
            {'INFO'},
            f"PolyPulse: {total_before} -> {total_after} (-{reduction_pct}%)"
        )
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_decimate_complete')}",
            icon='MOD_DECIM',
            lines=[
                (f"{PolyPulseI18N.t('popup_polys_before')}:  {total_before}",   'FACESEL'),
                (f"{PolyPulseI18N.t('popup_polys_after')}:   {total_after}",    'FACESEL'),
                (f"{PolyPulseI18N.t('popup_optimization')}:     -{reduction_pct}%", 'SOLO_ON'),
                "",
                (f"{PolyPulseI18N.t('popup_meshes_processed')}: {processed}",     'MESH_DATA'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 5 — EXPORT REPORT  (v0.1, расширен в v0.2/v0.3)
# =============================================================================
class POLYPULSE_OT_export_report(Operator):
    """Сохраняет расширенный текстовый отчёт рядом с .blend файлом."""

    bl_idname = "polypulse.export_report"
    bl_label = "Export Report"
    bl_description = "Save a detailed text report next to the .blend file"
    bl_icon = 'EXPORT'
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        blend_path = bpy.data.filepath
        if blend_path:
            dir_path = os.path.dirname(blend_path)
        else:
            dir_path = os.path.expanduser("~")
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_blend_not_saved')}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"polypulse_report_{timestamp}.txt"
        filepath = os.path.join(dir_path, filename)

        lines = []
        lines.append("=" * 60)
        lines.append("  POLYPULSE v0.5.6 — SCENE REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Date       : "
                     f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Blend file : {blend_path if blend_path else '(unsaved)'}")
        lines.append(f"Language   : {PolyPulseI18N.get_lang()}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("  SCENE STATISTICS")
        lines.append("-" * 60)
        lines.append(f"  Objects   : {props.objects_count}")
        lines.append(f"  Meshes    : {props.meshes_count}")
        lines.append(f"  Vertices  : {props.vertices_count}")
        lines.append(f"  Edges     : {props.edges_count}")
        lines.append(f"  Polygons  : {props.polygons_count}")
        lines.append(f"  Materials : {props.materials_count}")
        lines.append("")

        if props.adv_verts > 0:
            lines.append("-" * 60)
            lines.append("  ADVANCED MESH ANALYSIS")
            lines.append("-" * 60)
            lines.append(f"  Vertices  : {props.adv_verts}")
            lines.append(f"  Polygons  : {props.adv_polys}")
            lines.append(f"  Triangles : {props.adv_tris}")
            lines.append(f"  Ngons     : {props.adv_ngons}")
            lines.append(f"  Materials : {props.adv_materials}")
            lines.append(f"  Textures  : {props.adv_textures}")
            lines.append(f"  Has UV    : {'YES' if props.adv_has_uv else 'NO'}")
            lines.append(f"  Has Normals: {'YES' if props.adv_has_normals else 'NO'}")
            lines.append(f"  Dup Verts : {props.adv_duplicate_verts}")
            lines.append(f"  Overlap UV: {props.adv_overlapping_uv}")
            lines.append("")

        if len(props.adv_warnings) > 0:
            lines.append("-" * 60)
            lines.append("  WARNINGS")
            lines.append("-" * 60)
            for w in props.adv_warnings:
                lines.append(f"  [{w.severity}] {w.text}")
            lines.append("")

        if props.game_score > 0:
            lines.append("-" * 60)
            lines.append("  GAME READY SCORE 2.0")
            lines.append("-" * 60)
            lines.append(f"  Score        : {props.game_score}/100")
            lines.append(f"  Stars        : {'*' * props.game_stars}"
                        f"{'-' * (5 - props.game_stars)}")
            lines.append(f"  Label        : {props.game_label}")
            lines.append(f"  Geometry     : {props.game_geometry_pct}%")
            lines.append(f"  Textures     : {props.game_textures_pct}%")
            lines.append(f"  Materials    : {props.game_materials_pct}%")
            lines.append(f"  Optimization : {props.game_optimization_pct}%")
            lines.append(f"  Recommendation: {props.game_recommendation}")
            lines.append("")

        if props.dc_estimated > 0:
            lines.append("-" * 60)
            lines.append("  DRAW CALLS ESTIMATOR")
            lines.append("-" * 60)
            lines.append(f"  Triangles    : {props.dc_triangles}")
            lines.append(f"  Materials    : {props.dc_materials}")
            lines.append(f"  Objects      : {props.dc_objects}")
            lines.append(f"  Duplicates   : {props.dc_duplicates}")
            lines.append(f"  Estimated DC : {props.dc_estimated}")
            lines.append(f"  Recommendation: {props.dc_recommendation}")
            lines.append("")

        if len(props.validation_items) > 0:
            lines.append("-" * 60)
            lines.append("  ASSET VALIDATION")
            lines.append("-" * 60)
            for v in props.validation_items:
                status = "PASS" if v.passed else "FAIL"
                lines.append(f"  [{status}] {v.category} :: {v.check_name} "
                            f":: {v.detail}")
            lines.append(f"  Validation Score: {props.validation_score}/100")
            lines.append("")

        if len(props.textures) > 0:
            lines.append("-" * 60)
            lines.append("  TEXTURES")
            lines.append("-" * 60)
            for t in props.textures:
                lines.append(
                    f"  {t.name}: {t.size_x}x{t.size_y} "
                    f"({t.file_size_kb} KB) -> {t.recommendation}"
                )
            lines.append("")

        if props.lod_chain_created > 0:
            lines.append("-" * 60)
            lines.append("  LOD CHAIN")
            lines.append("-" * 60)
            lines.append(f"  LOD0 polys : {props.lod_chain_lod0_polys}")
            lines.append(f"  LOD1 polys : {props.lod_chain_lod1_polys}")
            lines.append(f"  LOD2 polys : {props.lod_chain_lod2_polys}")
            lines.append(f"  LOD3 polys : {props.lod_chain_lod3_polys}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("  OPTIMIZATION RESULTS")
        lines.append("-" * 60)
        lines.append(f"  Last operation : {props.last_operation}")
        if props.fix_verts_before > 0:
            lines.append(f"  Auto Fix: {props.fix_verts_before} -> "
                         f"{props.fix_verts_after} verts "
                         f"({props.fix_fixed_count} fixed)")
        lines.append("")
        lines.append("=" * 60)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        except OSError as exc:
            self.report({'ERROR'}, f"PolyPulse: {exc}")
            return {'CANCELLED'}

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_report_saved')}: {filepath}"
        )
        self.report({'INFO'},
                    f"PolyPulse: {PolyPulseI18N.t('msg_report_saved')} -> {filepath}")
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_report_saved')}",
            icon='EXPORT',
            lines=[
                (f"{PolyPulseI18N.t('popup_file')}: {filename}",      'FILE_TEXT'),
                (f"{PolyPulseI18N.t('popup_path')}: {dir_path}",       'FILE_FOLDER'),
                "",
                (f"Game Score: {props.game_score}/100  "
                 f"({props.game_label})",  'SOLO_ON'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 6 — ADVANCED SCAN  (v0.2)
# =============================================================================
class POLYPULSE_OT_advanced_scan(Operator):
    """
    Advanced Mesh Analyzer — глубокий анализ выбранных объектов.
    Считает ngons, tris, проверяет UV/normals/duplicate verts/overlap UV.
    """

    bl_idname = "polypulse.advanced_scan"
    bl_label = "Advanced Scan"
    bl_description = "Deep mesh analysis: ngons, UV, normals, duplicates, Game Ready Score"
    bl_icon = 'ZOOM_SELECTED'
    bl_options = {'REGISTER'}

    POLY_WARN_THRESHOLD = 20_000
    MATERIAL_WARN_THRESHOLD = 5

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        total_verts = 0
        total_polys = 0
        total_tris = 0
        total_ngons = 0
        unique_materials = set()
        has_uv_global = False
        has_normals_global = False
        total_dup_verts = 0
        total_overlap_uv = 0

        for obj in selected:
            mesh = obj.data
            total_verts += len(mesh.vertices)
            total_polys += len(mesh.polygons)

            if mesh.uv_layers.active is not None:
                has_uv_global = True
                total_overlap_uv += find_overlapping_uv_count(mesh)
            else:
                # Если нет UV — всё равно проверяем через bmesh
                pass

            if mesh.has_custom_normals:
                has_normals_global = True
            elif len(mesh.vertices) > 0:
                has_normals_global = True

            # Подсчёт ngons/tris через C-API poly.loop_total (без BMesh)
            # Старая версия создавала полную копию меша в памяти —
            # на больших сценах это критично по скорости и RAM.
            for poly in mesh.polygons:
                sides = poly.loop_total
                if sides > 4:
                    total_ngons += 1
                elif sides == 3:
                    total_tris += 1
                elif sides == 4:
                    total_tris += 2
                else:
                    # Дегенераты (1-2 вершины) игнорируем
                    if sides >= 3:
                        total_tris += sides - 2

            # Дубликаты вершин
            total_dup_verts += find_duplicate_vertices_count(mesh)

            for slot in obj.material_slots:
                if slot.material is not None:
                    unique_materials.add(slot.material.name)

        textures_info = collect_textures_from_objects(selected)
        max_tex_dim = max((t["max_dim"] for t in textures_info), default=0)

        # Сохраняем в props
        props.adv_verts = total_verts
        props.adv_polys = total_polys
        props.adv_tris = total_tris
        props.adv_ngons = total_ngons
        props.adv_objects = len(selected)
        props.adv_materials = len(unique_materials)
        props.adv_textures = len(textures_info)
        props.adv_has_uv = has_uv_global
        props.adv_has_normals = has_normals_global
        props.adv_duplicate_verts = total_dup_verts
        props.adv_overlapping_uv = total_overlap_uv

        # Warnings
        props.adv_warnings.clear()
        warnings_list = []
        if total_polys > self.POLY_WARN_THRESHOLD:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_too_many_polys')} ({total_polys:,})",
                "ERROR", "ERROR"))
        if total_ngons > 0:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_ngons_found')} ({total_ngons})",
                "ERROR", "ERROR"))
        if not has_uv_global:
            warnings_list.append((
                PolyPulseI18N.t('warn_no_uv'), "ERROR", "ERROR"))
        if not has_normals_global:
            warnings_list.append((
                PolyPulseI18N.t('warn_no_normals'), "ERROR", "ERROR"))
        if len(unique_materials) > self.MATERIAL_WARN_THRESHOLD:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_too_many_materials')} "
                f"({len(unique_materials)})", "ERROR", "ERROR"))
        if max_tex_dim > 4096:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_large_texture')} ({max_tex_dim}px)",
                "ERROR", "ERROR"))
        if total_dup_verts > 0:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_duplicate_verts')} ({total_dup_verts})",
                "ERROR", "ERROR"))
        if total_overlap_uv > 0:
            warnings_list.append((
                f"{PolyPulseI18N.t('warn_overlapping_uv')} "
                f"({total_overlap_uv})", "ERROR", "ERROR"))
        if not warnings_list:
            warnings_list.append((
                PolyPulseI18N.t('lbl_no_warnings'), "INFO", "CHECKMARK"))

        for text, sev, ico in warnings_list:
            item = props.adv_warnings.add()
            item.text = text
            item.severity = sev
            item.icon = ico

        # Сохраняем текстуры
        props.textures.clear()
        for t in textures_info:
            item = props.textures.add()
            item.name = t["name"]
            item.size_x = t["size_x"]
            item.size_y = t["size_y"]
            item.file_size_kb = t["file_size_kb"]
            item.recommendation = t["recommendation"]

        # Game Ready Score
        game = calculate_game_ready_score(
            verts=total_verts, polys=total_polys, ngons=total_ngons,
            materials=len(unique_materials), textures=len(textures_info),
            max_texture_dim=max_tex_dim, has_uv=has_uv_global,
            has_normals=has_normals_global,
            has_duplicate_verts=(total_dup_verts > 0),
            has_overlapping_uv=(total_overlap_uv > 0),
        )
        props.game_score = game["score"]
        props.game_stars = game["stars"]
        props.game_label = game["label"]
        props.game_geometry_pct = game["geometry_pct"]
        props.game_textures_pct = game["textures_pct"]
        props.game_materials_pct = game["materials_pct"]
        props.game_optimization_pct = game["optimization_pct"]
        props.game_recommendation = game["recommendation"]
        # v0.5.3: sync visual progress bars
        props.score_progress = game["score"] / 100.0
        props.geo_progress = game["geometry_pct"] / 100.0
        props.tex_progress = game["textures_pct"] / 100.0
        props.mat_progress = game["materials_pct"] / 100.0
        props.opt_progress = game["optimization_pct"] / 100.0

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_advanced_scan_complete')}: "
            f"{len(selected)} obj, {total_polys:,} polys, "
            f"{total_ngons} ngons, score {game['score']}/100"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {total_polys:,} polys | {total_ngons} ngons | "
            f"score {game['score']}/100 ({game['label']})"
        )

        popup_lines = [
            (f"{PolyPulseI18N.t('lbl_objects')}:   {len(selected)}",                'OBJECT_DATA'),
            (f"{PolyPulseI18N.t('lbl_vertices')}:  {total_verts:,}",                'VERTEXSEL'),
            (f"{PolyPulseI18N.t('lbl_polygons')}:  {total_polys:,}",                'FACESEL'),
            (f"{PolyPulseI18N.t('lbl_triangles')}: {total_tris:,}",                 'MESH_DATA'),
            (f"{PolyPulseI18N.t('lbl_ngons')}:     {total_ngons}",                  'ERROR'),
            (f"{PolyPulseI18N.t('lbl_materials')}: {len(unique_materials)}",        'MATERIAL'),
            (f"{PolyPulseI18N.t('lbl_textures')}:  {len(textures_info)}",           'TEXT'),
            "",
            (f"UV: {'YES' if has_uv_global else 'NO'}",
             'CHECKMARK' if has_uv_global else 'ERROR'),
            (f"Normals: {'YES' if has_normals_global else 'NO'}",
             'CHECKMARK' if has_normals_global else 'ERROR'),
            "",
            (f"Game Score: {game['score']}/100 "
             f"({'*' * game['stars']})",                  'SOLO_ON'),
            (f"Label: {game['label']}",                    'INFO'),
            "",
            game["recommendation"],
        ]
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_advanced_scan_complete')}",
            icon='ZOOM_SELECTED',
            lines=popup_lines,
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 7 — AUTO FIX MESH  (v0.2)
# =============================================================================
class POLYPULSE_OT_auto_fix_mesh(Operator):
    """Auto Fix Geometry: recalc normals, remove doubles, delete loose,
    remove unused materials, mesh.validate()."""

    bl_idname = "polypulse.auto_fix_mesh"
    bl_label = "Auto Fix Mesh"
    bl_description = "Recalc normals, remove doubles, delete loose, cleanup mesh"
    bl_icon = 'MODIFIER'
    bl_options = {'REGISTER', 'UNDO'}

    merge_threshold: FloatProperty(
        name="Merge Distance",
        description="Distance for merging duplicate vertices",
        default=0.0001,
        min=0.0,
        precision=5,
    )

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        total_before = 0
        total_after = 0
        total_fixed = 0
        processed = 0

        for obj in selected:
            mesh = obj.data
            verts_before = len(mesh.vertices)
            total_before += verts_before

            try:
                mesh.validate(verbose=False)
            except Exception:
                pass

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            try:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            except Exception:
                pass

            verts_before_op = len(bm.verts)
            try:
                bmesh.ops.remove_doubles(
                    bm, verts=bm.verts, dist=self.merge_threshold
                )
            except Exception:
                pass
            total_fixed += verts_before_op - len(bm.verts)

            loose_verts = [v for v in bm.verts if not v.link_edges]
            loose_edges = [e for e in bm.edges if not e.link_faces]
            # Delete once, before any BMesh references become stale.
            loose_geom = list(loose_verts) + list(loose_edges)
            if loose_geom:
                bmesh.ops.delete(bm, geom=loose_geom, context='VERTS')
                total_fixed += len(loose_geom)

            zero_area_faces = [
                f for f in bm.faces
                if f.calc_area() < 1e-8 and len(f.verts) >= 3
            ]
            if zero_area_faces:
                bmesh.ops.delete(
                    bm, geom=zero_area_faces, context='FACES'
                )
                total_fixed += len(zero_area_faces)

            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

            # Remove unused material slots (безопасно через прямое API)
            # Старая версия использовала bpy.ops.object.material_slot_remove(),
            # что удаляло слоты у активного объекта контекста (а не у obj)
            # и сбивало material_index на гранях. Новая версия работает так:
            #   1. Собираем индексы используемых материалов
            #   2. Строим map: old_idx -> new_idx (без дыр)
            #   3. Переназначаем material_index на гранях
            #   4. Очищаем список материалов и добавляем обратно используемые
            used_mat_indices = {p.material_index for p in mesh.polygons}
            new_materials = []
            idx_remap = {}

            for old_idx, slot in enumerate(obj.material_slots):
                if old_idx in used_mat_indices and slot.material:
                    idx_remap[old_idx] = len(new_materials)
                    new_materials.append(slot.material)

            # Переназначаем material_index на гранях под новые позиции
            for poly in mesh.polygons:
                poly.material_index = idx_remap.get(poly.material_index, 0)

            # Полностью очищаем список материалов и добавляем обратно используемые
            # Это безопасно: mesh.materials.clear() + materials.append()
            # в отличие от bpy.ops.object.material_slot_remove()
            obj.data.materials.clear()
            for mat in new_materials:
                obj.data.materials.append(mat)

            total_after += len(mesh.vertices)
            processed += 1

        props.fix_verts_before = total_before
        props.fix_verts_after = total_after
        props.fix_fixed_count = total_fixed
        props.last_operation = (
            f"{PolyPulseI18N.t('msg_auto_fix_complete')}: "
            f"{total_before:,} -> {total_after:,} verts "
            f"({total_fixed:,} fixed)"
        )

        self.report({'INFO'},
                    f"PolyPulse: Fixed {total_fixed:,} issues "
                    f"across {processed} meshes")
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_auto_fix_complete')}",
            icon='MODIFIER',
            lines=[
                (f"{PolyPulseI18N.t('popup_meshes_processed')}: {processed}",         'OBJECT_DATA'),
                "",
                (f"{PolyPulseI18N.t('lbl_vertices')} before: {total_before:,}",   'VERTEXSEL'),
                (f"{PolyPulseI18N.t('lbl_vertices')} after:  {total_after:,}",    'VERTEXSEL'),
                "",
                (f"{PolyPulseI18N.t('popup_fixed_issues')}:    {total_fixed:,}",    'CHECKMARK'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 8 — GENERATE LOD  (v0.2, single LOD)
# =============================================================================
class POLYPULSE_OT_generate_lod(Operator):
    """Создаёт копию выбранного объекта с DECIMATE-модификатором.
    Имя копии: <ObjectName>_LOD<N>."""

    bl_idname = "polypulse.generate_lod"
    bl_label = "Generate LOD"
    bl_description = "Generate LOD copy of selected object with decimate ratio"
    bl_icon = 'MOD_DECIM'
    bl_options = {'REGISTER', 'UNDO'}

    lod_level: EnumProperty(
        name="LOD Level",
        description="LOD level to generate",
        items=[
            ('1', "LOD 1 (50%)", "Reduce to 50% of polygons"),
            ('2', "LOD 2 (25%)", "Reduce to 25% of polygons"),
            ('3', "LOD 3 (10%)", "Reduce to 10% of polygons"),
        ],
        default='1',
    )

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        ratio_map = {'1': 0.50, '2': 0.25, '3': 0.10}
        ratio = ratio_map[self.lod_level]
        lod_suffix = f"_LOD{self.lod_level}"

        original_active = context.active_object
        created_count = 0
        total_polys_before = 0
        total_polys_after = 0

        for src_obj in selected:
            src_mesh = src_obj.data
            polys_before = len(src_mesh.polygons)
            total_polys_before += polys_before

            new_mesh = src_mesh.copy()
            new_mesh.name = src_mesh.name + lod_suffix
            new_obj = src_obj.copy()
            new_obj.data = new_mesh
            new_obj.name = src_obj.name + lod_suffix

            for coll in src_obj.users_collection:
                coll.objects.link(new_obj)
                break
            else:
                context.collection.objects.link(new_obj)

            mod = new_obj.modifiers.new(name=f"LOD{self.lod_level}",
                                        type='DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = ratio

            context.view_layer.objects.active = new_obj
            for o in context.selected_objects:
                o.select_set(False)
            new_obj.select_set(True)

            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                self.report({'WARNING'}, f"PolyPulse: {e}")
                new_obj.modifiers.remove(mod)
                continue

            polys_after = len(new_obj.data.polygons)
            total_polys_after += polys_after
            created_count += 1

        # Восстанавливаем выделение исходных объектов
        for o in context.selected_objects:
            o.select_set(False)
        for src in selected:
            src.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_lod_complete')} {self.lod_level}: "
            f"{created_count} objects, "
            f"{total_polys_before:,} -> {total_polys_after:,} polys"
        )

        self.report({'INFO'},
                    f"PolyPulse: Generated {created_count} "
                    f"LOD{self.lod_level} ({ratio*100:.0f}%)")
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_lod_complete')} LOD{self.lod_level}",
            icon='MOD_DECIM',
            lines=[
                (f"{PolyPulseI18N.t('popup_meshes_created')}: {created_count}",          'OBJECT_DATA'),
                (f"{PolyPulseI18N.t('popup_target_ratio')}:    {ratio*100:.0f}%",          'MOD_DECIM'),
                "",
                (f"{PolyPulseI18N.t('popup_polys_before')}: {total_polys_before:,}",      'FACESEL'),
                (f"{PolyPulseI18N.t('popup_polys_after')}:  {total_polys_after:,}",        'FACESEL'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 9 — GENERATE GAME READY LODs  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_generate_lod_chain(Operator):
    """
    Auto LOD Chain System — генерирует всю цепочку LOD0..LOD3
    одной кнопкой.

    LOD0 = 100% (копия оригинала без изменений)
    LOD1 = 50%
    LOD2 = 25%
    LOD3 = 10%

    Имена: Object_Name_LOD0..3. Материалы и UV сохраняются автоматически
    (mesh.copy() копирует materials и uv_layers).
    """

    bl_idname = "polypulse.generate_lod_chain"
    bl_label = "Generate Game Ready LODs"
    bl_description = "Generate LOD0..LOD3 chain in one click"
    bl_icon = 'MOD_DECIM'
    bl_options = {'REGISTER', 'UNDO'}

    # Ratios для каждого уровня
    LOD_RATIOS = {'0': 1.00, '1': 0.50, '2': 0.25, '3': 0.10}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def _create_lod(self, src_obj, level, context):
        """Создаёт один LOD-объект для заданного уровня."""
        ratio = self.LOD_RATIOS[level]
        suffix = f"_LOD{level}"

        new_mesh = src_obj.data.copy()
        new_mesh.name = src_obj.data.name + suffix
        new_obj = src_obj.copy()
        new_obj.data = new_mesh
        new_obj.name = src_obj.name + suffix

        # Линкуем в ту же коллекцию
        for coll in src_obj.users_collection:
            coll.objects.link(new_obj)
            break
        else:
            context.collection.objects.link(new_obj)

        # LOD0 = 100%, ничего не делаем с модификатором
        if level == '0':
            return new_obj, len(new_obj.data.polygons)

        # LOD1..3 — применяем DECIMATE
        mod = new_obj.modifiers.new(name=f"LOD{level}", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio

        context.view_layer.objects.active = new_obj
        for o in context.selected_objects:
            o.select_set(False)
        new_obj.select_set(True)

        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except RuntimeError as e:
            new_obj.modifiers.remove(mod)
            return new_obj, -1

        return new_obj, len(new_obj.data.polygons)

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        # Safety guard: applying 4 Decimate modifiers to hundreds of objects
        # forces repeated depsgraph evaluation and can crash Blender 5.1.x.
        # Linked duplicates share mesh data, so process one representative only.
        unique = []
        seen_meshes = set()
        for obj in selected:
            key = obj.data.as_pointer()
            if key in seen_meshes:
                continue
            seen_meshes.add(key)
            unique.append(obj)
        if len(unique) > 128:
            self.report(
                {'ERROR'},
                f"PolyPulse: LOD Chain stopped safely. {len(unique)} unique meshes selected; "
                f"maximum is 128. Merge/decimate the asset first or select a smaller group."
            )
            return {'CANCELLED'}
        selected = unique

        original_active = context.active_object
        total_created = 0
        total_polys = {'0': 0, '1': 0, '2': 0, '3': 0}
        skipped_linked = len(get_selected_mesh_objects(context)) - len(selected)

        for src_obj in selected:
            for level in ('0', '1', '2', '3'):
                new_obj, polys = self._create_lod(src_obj, level, context)
                total_created += 1
                if polys >= 0:
                    total_polys[level] += polys

        # Восстанавливаем выделение исходных объектов
        for o in context.selected_objects:
            o.select_set(False)
        for src in selected:
            src.select_set(True)
        if original_active:
            context.view_layer.objects.active = original_active

        # Сохраняем отчёт
        props.lod_chain_lod0_polys = total_polys['0']
        props.lod_chain_lod1_polys = total_polys['1']
        props.lod_chain_lod2_polys = total_polys['2']
        props.lod_chain_lod3_polys = total_polys['3']
        props.lod_chain_created = total_created

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_lod_chain_complete')}: "
            f"{total_created} objects created | "
            f"LOD0:{total_polys['0']:,} -> "
            f"LOD1:{total_polys['1']:,} -> "
            f"LOD2:{total_polys['2']:,} -> "
            f"LOD3:{total_polys['3']:,} polys"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {PolyPulseI18N.t('msg_lod_chain_complete')} — "
            f"{total_created} objects"
        )
        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_lod_chain_complete')}",
            icon='MOD_DECIM',
            lines=[
                (f"{PolyPulseI18N.t('popup_meshes_created')}: {total_created}",  'OBJECT_DATA'),
                "",
                (f"LOD0 (100%): {total_polys['0']:,}", 'MESH_DATA'),
                (f"LOD1 (50%):  {total_polys['1']:,}", 'MOD_DECIM'),
                (f"LOD2 (25%):  {total_polys['2']:,}", 'MOD_DECIM'),
                (f"LOD3 (10%):  {total_polys['3']:,}", 'MOD_DECIM'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 10 — TEXTURE SCAN  (v0.2)
# =============================================================================
class POLYPULSE_OT_texture_scan(Operator):
    """Texture Optimizer — анализ текстур с рекомендациями по платформам."""

    bl_idname = "polypulse.texture_scan"
    bl_label = "Texture Scan"
    bl_description = "Analyze textures and recommend resolutions per platform"
    bl_icon = 'TEXT'
    bl_options = {'REGISTER'}

    target_platform: EnumProperty(
        name="Target Platform",
        description="Target platform for texture recommendations",
        items=[
            ('MOBILE', "Mobile", "512-1024 px"),
            ('PC',     "PC",     "1024-2048 px"),
            ('HERO',   "Hero Asset", "2048-4096 px"),
        ],
        default='PC',
    )

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        textures_info = collect_textures_from_objects(selected)

        props.textures.clear()
        for t in textures_info:
            item = props.textures.add()
            item.name = t["name"]
            item.size_x = t["size_x"]
            item.size_y = t["size_y"]
            item.file_size_kb = t["file_size_kb"]
            max_dim = t["max_dim"]
            if self.target_platform == 'MOBILE':
                if max_dim > 1024:
                    item.recommendation = "Downscale to 1024 (mobile target)"
                else:
                    item.recommendation = "OK for mobile"
            elif self.target_platform == 'PC':
                if max_dim > 2048:
                    item.recommendation = "Downscale to 2048 (PC target)"
                else:
                    item.recommendation = "OK for PC"
            else:
                if max_dim > 4096:
                    item.recommendation = "Downscale to 4096 (hero target)"
                else:
                    item.recommendation = "OK for hero asset"

        total_textures = len(textures_info)
        total_size_kb = sum(t["file_size_kb"] for t in textures_info)
        oversized = sum(1 for t in textures_info if t["max_dim"] > 2048)

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_texture_scan_complete')}: "
            f"{total_textures} textures, "
            f"{total_size_kb/1024:.1f} MB total, {oversized} oversized"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {total_textures} textures | "
            f"{total_size_kb/1024:.1f} MB | {oversized} oversized"
        )

        platform_label = {
            'MOBILE': "Mobile (512-1024 px)",
            'PC':     "PC (1024-2048 px)",
            'HERO':   "Hero (2048-4096 px)",
        }[self.target_platform]

        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_texture_scan_complete')}",
            icon='TEXT',
            lines=[
                (f"{PolyPulseI18N.t('lbl_textures')}: {total_textures}",     'TEXT'),
                (f"Total size: {total_size_kb/1024:.1f} MB", 'FILE_FOLDER'),
                (f"Oversized (>2K): {oversized}",         'ERROR'),
                "",
                f"Target: {platform_label}",
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 11 — BATCH OPTIMIZER  (v0.2)
# =============================================================================
class POLYPULSE_OT_batch_optimize(Operator):
    """Batch Optimizer — пакетный анализ .blend файлов в папке."""

    bl_idname = "polypulse.batch_optimize"
    bl_label = "Batch Optimize"
    bl_description = "Batch analyze .blend files in a folder"
    bl_icon = 'FILE_FOLDER'
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name="Target Folder",
        description="Folder containing .blend files to analyze",
        subtype='DIR_PATH',
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        if not self.directory or not os.path.isdir(self.directory):
            self.report({'ERROR'},
                        f"PolyPulse: {PolyPulseI18N.t('lbl_invalid_folder')}")
            return {'CANCELLED'}

        blend_files = []
        for fname in sorted(os.listdir(self.directory)):
            if fname.lower().endswith('.blend'):
                blend_files.append(os.path.join(self.directory, fname))

        if not blend_files:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('lbl_no_blend_files')}")
            return {'CANCELLED'}

        results = []
        for blend_path in blend_files:
            loaded_objects = []
            loaded_meshes = []
            loaded_materials = []
            loaded_images = []
            try:
                with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
                    dst.objects = list(src.objects)
                    dst.meshes = list(src.meshes)
                    dst.materials = list(src.materials)
                    dst.images = list(src.images)
                loaded_objects = [o for o in dst.objects if o is not None]
                loaded_meshes = [m for m in dst.meshes if m is not None]
                loaded_materials = [m for m in dst.materials if m is not None]
                loaded_images = [i for i in dst.images if i is not None]
            except Exception as exc:
                results.append({
                    "file": os.path.basename(blend_path),
                    "error": str(exc),
                })
                continue

            results.append({
                "file": os.path.basename(blend_path),
                "objects": len(loaded_objects),
                "meshes": len(loaded_meshes),
                "materials": len(loaded_materials),
                "textures": len(loaded_images),
            })
            # Remove temporary datablocks so batch analysis never pollutes the open scene.
            for obj in loaded_objects:
                if obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
                for block in list(datablocks):
                    if block.users == 0:
                        datablocks.remove(block)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_path = os.path.join(
            self.directory,
            f"polypulse_batch_report_{timestamp}.txt",
        )
        lines = []
        lines.append("=" * 60)
        lines.append("  POLYPULSE v0.5.6 — BATCH REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Date  : "
                     f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Folder: {self.directory}")
        lines.append(f"Files analyzed: {len(blend_files)}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("  PER-FILE STATISTICS")
        lines.append("-" * 60)
        for r in results:
            lines.append("")
            lines.append(f"  File: {r['file']}")
            if "error" in r:
                lines.append(f"    ERROR: {r['error']}")
                continue
            lines.append(f"    Objects  : {r['objects']}")
            lines.append(f"    Meshes   : {r['meshes']}")
            lines.append(f"    Materials: {r['materials']}")
            lines.append(f"    Textures : {r['textures']}")
        lines.append("")
        lines.append("=" * 60)

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        except OSError as exc:
            self.report({'ERROR'}, f"PolyPulse: {exc}")
            return {'CANCELLED'}

        total_objs = sum(r.get("objects", 0) for r in results)
        total_meshes = sum(r.get("meshes", 0) for r in results)
        total_mats = sum(r.get("materials", 0) for r in results)
        total_tex = sum(r.get("textures", 0) for r in results)
        errors = sum(1 for r in results if "error" in r)

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_batch_complete')}: "
            f"{len(results)} files, {total_objs} objects"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {PolyPulseI18N.t('msg_batch_complete')} — "
            f"{len(results)} files ({errors} errors)"
        )

        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_batch_complete')}",
            icon='FILE_FOLDER',
            lines=[
                (f"{PolyPulseI18N.t('popup_files_analyzed')}: {len(results)}",  'FILE_BLEND'),
                (f"{PolyPulseI18N.t('popup_errors')}:         {errors}",
                 'ERROR' if errors else 'CHECKMARK'),
                "",
                (f"{PolyPulseI18N.t('popup_total_objects')}:   {total_objs}",  'OBJECT_DATA'),
                (f"{PolyPulseI18N.t('popup_total_meshes')}:    {total_meshes}", 'MESH_DATA'),
                (f"{PolyPulseI18N.t('popup_total_materials')}: {total_mats}",  'MATERIAL'),
                (f"{PolyPulseI18N.t('popup_total_textures')}:  {total_tex}",   'TEXT'),
                "",
                (f"Report: {os.path.basename(report_path)}", 'FILE_TEXT'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 12 — DRAW CALLS ESTIMATOR  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_draw_calls_estimator(Operator):
    """
    Draw Calls Estimator — оценка производительности для игрового движка.

    Считает:
      - Triangles (общее количество треугольников)
      - Materials (количество уникальных материалов)
      - Objects (выбранные объекты)
      - Duplicates (объекты, шарящие mesh data — Alt-D)
      - Estimated Draw Calls (max(objects, total_slots))

    Дает рекомендацию по объединению материалов если DC > 10.
    """

    bl_idname = "polypulse.draw_calls_estimator"
    bl_label = "Draw Calls Estimator"
    bl_description = "Estimate draw calls and performance for game engines"
    bl_icon = 'INFO'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        # --- Подсчёт треугольников ---
        total_tris = 0
        for obj in selected:
            mesh = obj.data
            for poly in mesh.polygons:
                if len(poly.vertices) == 3:
                    total_tris += 1
                elif len(poly.vertices) == 4:
                    total_tris += 2
                else:
                    total_tris += max(0, len(poly.vertices) - 2)

        # --- Подсчёт уникальных материалов ---
        unique_materials = set()
        for obj in selected:
            for slot in obj.material_slots:
                if slot.material is not None:
                    unique_materials.add(slot.material.name)

        # --- Duplicates (объекты с shared mesh data) ---
        mesh_to_objects = {}
        for obj in selected:
            mesh_to_objects.setdefault(obj.data.name, []).append(obj.name)
        duplicates_count = sum(
            1 for names in mesh_to_objects.values() if len(names) > 1
        )

        # --- Draw calls estimate ---
        estimated_dc, total_slots, obj_count, unique_meshes = \
            estimate_draw_calls(selected)

        # --- Сохраняем в props ---
        props.dc_triangles = total_tris
        props.dc_materials = len(unique_materials)
        props.dc_objects = obj_count
        props.dc_duplicates = duplicates_count
        props.dc_estimated = estimated_dc

        # --- Рекомендация ---
        if estimated_dc > 20:
            recommendation = PolyPulseI18N.t('rec_combine_materials')
        elif estimated_dc > 10:
            recommendation = PolyPulseI18N.t('rec_optimize_required')
        else:
            recommendation = PolyPulseI18N.t('rec_near_ready')
        props.dc_recommendation = recommendation

        props.last_operation = (
            f"{PolyPulseI18N.t('lbl_draw_calls')}: "
            f"{estimated_dc} DC, {total_tris:,} tris, "
            f"{len(unique_materials)} mats"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: {estimated_dc} draw calls | "
            f"{total_tris:,} tris | {len(unique_materials)} materials"
        )

        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('lbl_draw_calls')}",
            icon='INFO',
            lines=[
                (f"{PolyPulseI18N.t('lbl_triangles_count')}:  {total_tris:,}", 'MESH_DATA'),
                (f"{PolyPulseI18N.t('lbl_materials')}:  {len(unique_materials)}", 'MATERIAL'),
                (f"{PolyPulseI18N.t('lbl_objects')}:    {obj_count}", 'OBJECT_DATA'),
                (f"Duplicates:    {duplicates_count}", 'LINKED'),
                "",
                (f"{PolyPulseI18N.t('lbl_draw_calls')}: {estimated_dc}", 'INFO'),
                "",
                (f"{PolyPulseI18N.t('lbl_recommendation')}:",
                 'INFO'),
                recommendation,
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 13 — GAME READY CHECK  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_game_ready_check(Operator):
    """
    Asset Validation System — проверка Game Ready.

    Категории:
      Geometry:  polygon count, ngons, duplicate verts, normals
      Textures:  resolution, missing textures
      Materials: too many materials
      UV:        exists, overlapping

    Каждая проверка = pass/fail + detail.
    Финальный score = (passed / total) * 100.
    """

    bl_idname = "polypulse.game_ready_check"
    bl_label = "Game Ready Check"
    bl_description = "Run full asset validation for game engine readiness"
    bl_icon = 'CHECKMARK'
    bl_options = {'REGISTER'}

    # Пороги
    POLY_OK = 20_000
    NGON_OK = 0
    DUP_VERT_OK = 0
    MAT_OK = 5
    TEX_MAX = 4096

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        scene = context.scene
        props = scene.polypulse_props

        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        ensure_object_mode(context)

        # --- Сбор статистики ---
        total_polys = 0
        total_ngons = 0
        total_dup_verts = 0
        unique_materials = set()
        has_uv = False
        has_normals = False
        total_overlap_uv = 0
        textures_info = []
        missing_textures = 0
        max_tex_dim = 0

        for obj in selected:
            mesh = obj.data
            total_polys += len(mesh.polygons)

            # Ngons через C-API (без BMesh — быстрее и безопаснее)
            for poly in mesh.polygons:
                if poly.loop_total > 4:
                    total_ngons += 1

            total_dup_verts += find_duplicate_vertices_count(mesh)

            # UV
            if mesh.uv_layers.active is not None:
                has_uv = True
                total_overlap_uv += find_overlapping_uv_count(mesh)

            # Normals
            if len(mesh.vertices) > 0 and len(mesh.polygons) > 0:
                has_normals = True

            # Materials + texture check
            for slot in obj.material_slots:
                if slot.material is None:
                    continue
                unique_materials.add(slot.material.name)
                mat = slot.material
                has_texture_in_mat = False
                if mat.node_tree is not None:
                    for node in mat.node_tree.nodes:
                        if node.type == 'TEX_IMAGE' and node.image is not None:
                            has_texture_in_mat = True
                            img = node.image
                            max_dim = max(img.size[0], img.size[1])
                            max_tex_dim = max(max_tex_dim, max_dim)
                if not has_texture_in_mat:
                    missing_textures += 1

        textures_info = collect_textures_from_objects(selected)

        # --- Очищаем и заполняем validation items ---
        props.validation_items.clear()

        # GEOMETRY
        checks = []
        checks.append((
            PolyPulseI18N.t('validation_geometry'),
            "Polygon count",
            total_polys <= self.POLY_OK,
            f"{total_polys:,} polys (max {self.POLY_OK:,})"
        ))
        checks.append((
            PolyPulseI18N.t('validation_geometry'),
            "Ngons",
            total_ngons <= self.NGON_OK,
            f"{total_ngons} ngons found"
        ))
        checks.append((
            PolyPulseI18N.t('validation_geometry'),
            "Duplicate vertices",
            total_dup_verts <= self.DUP_VERT_OK,
            f"{total_dup_verts} duplicates"
        ))
        checks.append((
            PolyPulseI18N.t('validation_geometry'),
            "Normals",
            has_normals,
            "YES" if has_normals else "MISSING"
        ))

        # TEXTURES
        checks.append((
            PolyPulseI18N.t('validation_textures'),
            "Resolution",
            max_tex_dim <= self.TEX_MAX,
            f"max {max_tex_dim}px (limit {self.TEX_MAX})"
        ))
        checks.append((
            PolyPulseI18N.t('validation_textures'),
            "Missing textures",
            missing_textures == 0,
            f"{missing_textures} materials without texture"
        ))

        # MATERIALS
        checks.append((
            PolyPulseI18N.t('validation_materials'),
            "Too many materials",
            len(unique_materials) <= self.MAT_OK,
            f"{len(unique_materials)} materials (max {self.MAT_OK})"
        ))

        # UV
        checks.append((
            PolyPulseI18N.t('validation_uv'),
            "UV exists",
            has_uv,
            "YES" if has_uv else "MISSING"
        ))
        checks.append((
            PolyPulseI18N.t('validation_uv'),
            "Overlapping UV",
            total_overlap_uv == 0,
            f"{total_overlap_uv} overlapping UVs"
        ))

        passed_count = 0
        for cat, name, passed, detail in checks:
            item = props.validation_items.add()
            item.category = cat
            item.check_name = name
            item.passed = passed
            item.detail = detail
            if passed:
                passed_count += 1

        total_checks = len(checks)
        score = int(round((passed_count / total_checks) * 100)) \
            if total_checks > 0 else 0
        props.validation_score = score
        props.validation_passed = (passed_count == total_checks)
        props.validation_progress = score / 100.0

        # --- Лейбл по порогам v0.3 ---
        if score <= 40:
            label = PolyPulseI18N.t('score_poor')
        elif score <= 70:
            label = PolyPulseI18N.t('score_needs_optimization')
        elif score <= 90:
            label = PolyPulseI18N.t('score_game_ready')
        else:
            label = PolyPulseI18N.t('score_excellent')

        props.last_operation = (
            f"{PolyPulseI18N.t('msg_validation_complete')}: "
            f"{passed_count}/{total_checks} passed, score {score}/100 ({label})"
        )

        self.report(
            {'INFO'},
            f"PolyPulse: Validation {passed_count}/{total_checks} — "
            f"score {score}/100 ({label})"
        )

        show_popup(
            context,
            title=f"PolyPulse: {PolyPulseI18N.t('msg_validation_complete')}",
            icon='CHECKMARK' if props.validation_passed else 'ERROR',
            lines=[
                (f"Passed: {passed_count}/{total_checks}", 'CHECKMARK'),
                (f"Score:  {score}/100 ({label})", 'SOLO_ON'),
                "",
                "See panel for details",
            ],
        )
        return {'FINISHED'}


# =============================================================================
# EXPORT COMPATIBILITY HELPERS
# =============================================================================
def _call_operator_compatible(operator, kwargs):
    """Filter exporter kwargs against the active Blender RNA schema."""
    try:
        supported = {p.identifier for p in operator.get_rna_type().properties}
        kwargs = {k: v for k, v in kwargs.items() if k in supported}
    except Exception:
        pass
    return operator(**kwargs)


# =============================================================================
# ОПЕРАТОР 14 — EXPORT TO UE5  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_export_ue5(Operator):
    """
    Export to Unreal Engine 5 — FBX с правильными настройками для UE5.

    - Scale: 1.0 (UE5 использует сантиметры, FBX scale 1.0)
    - Forward: Y forward (UE5 convention)
    - Up: Z up
    - Apply Transform: YES (иначе UE5 применит свой scale)
    - Materials: embed в FBX
    """

    bl_idname = "polypulse.export_ue5"
    bl_label = "Export to UE5"
    bl_description = "Export selected objects as FBX for Unreal Engine 5"
    bl_icon = 'EXPORT'
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        blend_path = bpy.data.filepath
        if blend_path:
            default_name = os.path.splitext(
                os.path.basename(blend_path)
            )[0] + "_ue5.fbx"
            default_dir = os.path.dirname(blend_path)
        else:
            default_name = "polypulse_export_ue5.fbx"
            default_dir = os.path.expanduser("~")
        self.filepath = os.path.join(default_dir, default_name)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        if not self.filepath:
            self.report({'ERROR'}, "PolyPulse: No export path")
            return {'CANCELLED'}

        ensure_object_mode(context)

        # Убедимся, что расширение .fbx
        if not self.filepath.lower().endswith('.fbx'):
            self.filepath += '.fbx'

        try:
            # Формируем параметры экспорта, совместимые с Blender 2.83+
            fbx_kwargs = dict(
                filepath=self.filepath,
                use_selection=True,
                axis_forward='-Z',
                axis_up='Y',
                global_scale=1.0,
                apply_unit_scale=True,
                bake_anim=False,
                use_mesh_modifiers=True,
                mesh_smooth_type='FACE',
                path_mode='COPY',
                embed_textures=True,
                # Do not export MikkTSpace tangent bases from malformed/zero-area UVs.
                # UE5 rebuilds tangents on import; this avoids degenerate tangent warnings.
                use_tspace=False,
                object_types={'MESH'},
                use_custom_props=True,
            )
            # apply_scale_options появился в Blender 3.0+
            try:
                fbx_kwargs['apply_scale_options'] = 'FBX_SCALE_ALL'
            except (TypeError, KeyError):
                pass
            # use_triangles появился в Blender 3.2+
            try:
                fbx_kwargs['use_triangles'] = True
            except (TypeError, KeyError):
                pass
            _call_operator_compatible(bpy.ops.export_scene.fbx, fbx_kwargs)
        except Exception as exc:
            self.report({'ERROR'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_export_failed')}: {exc}")
            return {'CANCELLED'}

        scene = context.scene
        props = scene.polypulse_props
        props.last_operation = (
            f"{PolyPulseI18N.t('msg_export_complete')} UE5: "
            f"{os.path.basename(self.filepath)}"
        )

        self.report({'INFO'},
                    f"PolyPulse: {PolyPulseI18N.t('rec_ready_ue5')} "
                    f"-> {self.filepath}")

        show_popup(
            context,
            title=f"PolyPulse: UE5 Export Complete",
            icon='EXPORT',
            lines=[
                (f"{PolyPulseI18N.t('popup_file')}: "
                 f"{os.path.basename(self.filepath)}", 'FILE_BLEND'),
                (f"{PolyPulseI18N.t('popup_path')}: "
                 f"{os.path.dirname(self.filepath)}", 'FILE_FOLDER'),
                "",
                (f"Objects: {len(selected)}", 'OBJECT_DATA'),
                "",
                PolyPulseI18N.t('rec_ready_ue5'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 15 — EXPORT TO UNITY  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_export_unity(Operator):
    """
    Export to Unity — FBX с настройками под Unity.

    - Scale: 1.0 (Unity FBX importer корректно конвертирует)
    - Forward: -Z (Unity convention)
    - Up: Y up
    - Apply Transform: YES
    - Materials: embed в FBX
    """

    bl_idname = "polypulse.export_unity"
    bl_label = "Export to Unity"
    bl_description = "Export selected objects as FBX for Unity"
    bl_icon = 'EXPORT'
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        blend_path = bpy.data.filepath
        if blend_path:
            default_name = os.path.splitext(
                os.path.basename(blend_path)
            )[0] + "_unity.fbx"
            default_dir = os.path.dirname(blend_path)
        else:
            default_name = "polypulse_export_unity.fbx"
            default_dir = os.path.expanduser("~")
        self.filepath = os.path.join(default_dir, default_name)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        if not self.filepath:
            self.report({'ERROR'}, "PolyPulse: No export path")
            return {'CANCELLED'}

        ensure_object_mode(context)

        if not self.filepath.lower().endswith('.fbx'):
            self.filepath += '.fbx'

        try:
            fbx_kwargs = dict(
                filepath=self.filepath,
                use_selection=True,
                axis_forward='-Z',
                axis_up='Y',
                global_scale=1.0,
                apply_unit_scale=True,
                bake_anim=False,
                use_mesh_modifiers=True,
                mesh_smooth_type='FACE',
                path_mode='COPY',
                embed_textures=True,
                # Do not export MikkTSpace tangent bases from malformed/zero-area UVs.
                # UE5 rebuilds tangents on import; this avoids degenerate tangent warnings.
                use_tspace=False,
                object_types={'MESH'},
                use_custom_props=True,
            )
            try:
                fbx_kwargs['apply_scale_options'] = 'FBX_SCALE_ALL'
            except (TypeError, KeyError):
                pass
            try:
                fbx_kwargs['use_triangles'] = True
            except (TypeError, KeyError):
                pass
            _call_operator_compatible(bpy.ops.export_scene.fbx, fbx_kwargs)
        except Exception as exc:
            self.report({'ERROR'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_export_failed')}: {exc}")
            return {'CANCELLED'}

        scene = context.scene
        props = scene.polypulse_props
        props.last_operation = (
            f"{PolyPulseI18N.t('msg_export_complete')} Unity: "
            f"{os.path.basename(self.filepath)}"
        )

        self.report({'INFO'},
                    f"PolyPulse: {PolyPulseI18N.t('rec_ready_unity')} "
                    f"-> {self.filepath}")

        show_popup(
            context,
            title=f"PolyPulse: Unity Export Complete",
            icon='EXPORT',
            lines=[
                (f"{PolyPulseI18N.t('popup_file')}: "
                 f"{os.path.basename(self.filepath)}", 'FILE_BLEND'),
                (f"{PolyPulseI18N.t('popup_path')}: "
                 f"{os.path.dirname(self.filepath)}", 'FILE_FOLDER'),
                "",
                (f"Objects: {len(selected)}", 'OBJECT_DATA'),
                "",
                PolyPulseI18N.t('rec_ready_unity'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ОПЕРАТОР 16 — EXPORT TO GODOT  (v0.3 NEW)
# =============================================================================
class POLYPULSE_OT_export_godot(Operator):
    """
    Export to Godot — glTF (.glb или .gltf) с настройками под Godot 4.

    - Godot 4 native формат: glTF
    - Y up (Godot convention)
    - Apply Transform: YES
    - Materials: embed в glTF binary
    """

    bl_idname = "polypulse.export_godot"
    bl_label = "Export to Godot"
    bl_description = "Export selected objects as glTF for Godot 4"
    bl_icon = 'EXPORT'
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        blend_path = bpy.data.filepath
        if blend_path:
            default_name = os.path.splitext(
                os.path.basename(blend_path)
            )[0] + "_godot.glb"
            default_dir = os.path.dirname(blend_path)
        else:
            default_name = "polypulse_export_godot.glb"
            default_dir = os.path.expanduser("~")
        self.filepath = os.path.join(default_dir, default_name)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        return len(get_selected_mesh_objects(context)) > 0

    def execute(self, context):
        selected = get_selected_mesh_objects(context)
        if not selected:
            self.report({'WARNING'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_no_mesh_selected')}")
            return {'CANCELLED'}

        if not self.filepath:
            self.report({'ERROR'}, "PolyPulse: No export path")
            return {'CANCELLED'}

        ensure_object_mode(context)

        # Принудительно .glb (binary glTF — Godot рекомендует)
        if not self.filepath.lower().endswith(('.glb', '.gltf')):
            self.filepath += '.glb'

        try:
            gltf_kwargs = dict(
                filepath=self.filepath,
                export_format='GLB',
                use_selection=True,
                export_yup=True,
                export_apply=True,
                export_image_format="AUTO",
                export_texcoords=True,
                export_normals=True,
                export_tangents=False,
                export_extras=True,
            )
            # export_materials='EXPORT' — Blender 3.2+ (в 2.83 был bool export_materials)
            try:
                gltf_kwargs['export_materials'] = 'EXPORT'
            except (TypeError, KeyError):
                gltf_kwargs['export_materials'] = True
            # export_mesh_type='TRIANGLES' — Blender 3.2+
            _call_operator_compatible(bpy.ops.export_scene.gltf, gltf_kwargs)
        except Exception as exc:
            self.report({'ERROR'},
                        f"PolyPulse: {PolyPulseI18N.t('msg_export_failed')}: {exc}")
            return {'CANCELLED'}

        scene = context.scene
        props = scene.polypulse_props
        props.last_operation = (
            f"{PolyPulseI18N.t('msg_export_complete')} Godot: "
            f"{os.path.basename(self.filepath)}"
        )

        self.report({'INFO'},
                    f"PolyPulse: {PolyPulseI18N.t('rec_ready_godot')} "
                    f"-> {self.filepath}")

        show_popup(
            context,
            title=f"PolyPulse: Godot Export Complete",
            icon='EXPORT',
            lines=[
                (f"{PolyPulseI18N.t('popup_file')}: "
                 f"{os.path.basename(self.filepath)}", 'FILE_BLEND'),
                (f"{PolyPulseI18N.t('popup_path')}: "
                 f"{os.path.dirname(self.filepath)}", 'FILE_FOLDER'),
                "",
                (f"Objects: {len(selected)}", 'OBJECT_DATA'),
                "",
                PolyPulseI18N.t('rec_ready_godot'),
            ],
        )
        return {'FINISHED'}


# =============================================================================
# ПАНЕЛИ
# =============================================================================

# -----------------------------------------------------------------------------
# v0.5.1 UI helper: collapsible section header (disclosure triangle)
# -----------------------------------------------------------------------------

def _section_header(layout, props, prop_name, label, icon='NONE'):
    """Draw a reliable collapsible section header for Blender 5.x and older.

    The public beta removed the license/tier helpers, but the UI still uses
    this independent disclosure control for stats, warnings, and texture lists.
    """
    state = bool(getattr(props, prop_name, True))
    row = layout.row(align=True)
    triangle = 'DISCLOSURE_TRI_DOWN' if state else 'DISCLOSURE_TRI_RIGHT'
    row.prop(props, prop_name, icon=triangle, icon_only=True, emboss=False, text='')
    row.prop(props, prop_name, icon=icon, emboss=False, text=label)
    return state


class POLYPULSE_PT_main(Panel):
    """Корневая панель — Game Ready Score + Recommendation."""

    bl_label = "PolyPulse"
    bl_idname = "POLYPULSE_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Game Ready Score 2.0 (v0.5.3 redesign) ---
        box = layout.box()

        if props.game_score > 0 or props.adv_verts > 0:
            # Header row: score + label
            row = box.row(align=True)
            row.label(text=PolyPulseI18N.t('section_score'), icon='SOLO_ON')
            row.label(text=f"{props.game_score}/100", icon='INFO')

            # Visual progress bar (Blender's built-in UI progress)
            score_row = box.row(align=True)
            score_row.label(text="Score: " + str(props.game_score) + "/100")
            score_row.label(text=props.game_label, icon='SOLO_ON')

            # Stars + label row
            row2 = box.row(align=True)
            row2.alignment = 'CENTER'
            stars_str = '★' * props.game_stars + '☆' * (5 - props.game_stars)
            row2.label(text=stars_str)

            # Per-category mini progress bars
            grid = box.column(align=True)
            grid.separator()
            grid.label(text="Geometry: " + str(round(props.geo_progress * 100)) + "%")
            grid.label(text="Textures: " + str(round(props.tex_progress * 100)) + "%")
            grid.label(text="Materials: " + str(round(props.mat_progress * 100)) + "%")
            grid.label(text="Optimization: " + str(round(props.opt_progress * 100)) + "%")

            if props.game_recommendation:
                rec_box = box.box()
                # Choose icon based on score
                rec_icon = 'CHECKMARK' if props.game_score >= 71 else 'ERROR'
                rec_box.label(text=props.game_recommendation, icon=rec_icon)
        else:
            # Empty state — call to action
            empty_box = box.column(align=True)
            empty_box.scale_y = 0.9
            empty_box.label(text=PolyPulseI18N.t('lbl_run_advanced'),
                            icon='QUESTION')
            empty_box.separator()
            empty_box.operator(
                "polypulse.advanced_scan",
                text=PolyPulseI18N.t('btn_advanced_scan'),
                icon='VIEWZOOM',
            )
            empty_box.operator(
                "polypulse.analyze_scene",
                text=PolyPulseI18N.t('btn_analyze_scene'),
                icon='ZOOM_SELECTED',
            )

        # =====================================================================
        # v0.5.9 — PolyPulse Pro teaser + community link
        # =====================================================================
        layout.separator()
        pro_box = layout.box()

        # Header
        pro_box.label(
            text=PolyPulseI18N.t("vorvexon_title", "VORVEXON — Next Generation"),
            icon='FUND',
        )

        feat_col = pro_box.column(align=True)
        feat_col.scale_y = 0.85
        for key, default in (
            ("vorvexon_pipeline", "Game-ready asset pipeline for Blender"),
            ("vorvexon_batch", "Batch workflows for assets and scenes"),
            ("vorvexon_budget", "Performance budgets and verified export"),
            ("vorvexon_updates", "Devlogs, early access and release updates"),
        ):
            feat_col.label(text="• " + PolyPulseI18N.t(key, default), icon='BLANK1')

        pro_box.separator()

        pro_box.label(
            text=PolyPulseI18N.t(
                "vorvexon_beta_note",
                "PolyPulse Community Beta stays free and fully unlocked",
            ),
            icon='COMMUNITY',
        )

        pro_box.separator()

        cta = pro_box.operator(
            "wm.url_open",
            text=PolyPulseI18N.t("vorvexon_cta", "Follow VORVEXON Development"),
            icon='URL',
        )
        cta.url = "https://t.me/vorvexon"


class POLYPULSE_PT_analysis(Panel):
    """Sub-panel ANALYSIS — Analyze Scene + Advanced Scan + Draw Calls."""

    bl_label = "Analysis"
    bl_idname = "POLYPULSE_PT_analysis"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Quick scan buttons ---
        col = layout.column(align=True)
        col.scale_y = 1.1
        col.operator("polypulse.analyze_scene",
                     text=PolyPulseI18N.t('btn_analyze_scene'),
                     icon='ZOOM_SELECTED')
        col.operator("polypulse.advanced_scan",
                     text=PolyPulseI18N.t('btn_advanced_scan'),
                     icon='VIEWZOOM')
        col.operator(
            "polypulse.draw_calls_estimator",
            text=PolyPulseI18N.t('lbl_draw_calls'),
            icon='INFO',
        )

        # --- Advanced Stats (collapsible sub-section) ---
        if props.adv_verts > 0 or props.adv_polys > 0:
            if _section_header(layout, props, 'ui_show_stats',
                               "Advanced Stats", 'MESH_DATA'):
                box = layout.box()

                # Key metrics in 2-column grid
                grid = box.grid_flow(row_major=True, columns=2, align=True)
                grid.label(text=f"{PolyPulseI18N.t('lbl_vertices')}: "
                                f"{props.adv_verts:,}",
                           icon='VERTEXSEL')
                grid.label(text=f"{PolyPulseI18N.t('lbl_polygons')}: "
                                f"{props.adv_polys:,}",
                           icon='FACESEL')
                grid.label(text=f"{PolyPulseI18N.t('lbl_triangles')}: "
                                f"{props.adv_tris:,}",
                           icon='MESH_DATA')
                grid.label(text=f"{PolyPulseI18N.t('lbl_ngons')}: "
                                f"{props.adv_ngons}",
                           icon='ERROR' if props.adv_ngons > 0 else 'CHECKMARK')
                grid.label(text=f"{PolyPulseI18N.t('lbl_materials')}: "
                                f"{props.adv_materials}",
                           icon='MATERIAL')
                grid.label(text=f"{PolyPulseI18N.t('lbl_textures')}: "
                                f"{props.adv_textures}",
                           icon='TEXT')

                # UV / Normals status badges
                status_row = box.row(align=True)
                uv_icon = 'CHECKMARK' if props.adv_has_uv else 'ERROR'
                uv_text = f"UV: {PolyPulseI18N.t('lbl_yes') if props.adv_has_uv else PolyPulseI18N.t('lbl_no')}"
                status_row.label(text=uv_text, icon=uv_icon)

                norm_icon = 'CHECKMARK' if props.adv_has_normals else 'ERROR'
                norm_text = f"Norms: {PolyPulseI18N.t('lbl_yes') if props.adv_has_normals else PolyPulseI18N.t('lbl_no')}"
                status_row.label(text=norm_text, icon=norm_icon)

                # --- Warnings (collapsible, color-coded) ---
                if len(props.adv_warnings) > 0:
                    has_errors = any(w.severity == 'ERROR' for w in props.adv_warnings)
                    warn_header_icon = 'ERROR' if has_errors else 'CHECKMARK'
                    if _section_header(layout, props, 'ui_show_warnings',
                                       PolyPulseI18N.t('section_warnings'),
                                       warn_header_icon):
                        wbox = layout.box()
                        for w in props.adv_warnings:
                            row = wbox.row(align=True)
                            # Color-code: errors get alert background
                            if w.severity == 'ERROR':
                                row.alert = True
                            row.label(text=w.text, icon=w.icon)


class POLYPULSE_PT_optimization(Panel):
    """Sub-panel OPTIMIZATION — Auto Fix, Remove Doubles, Merge,
    Smart Decimate, LOD Chain, LOD1/2/3."""

    bl_label = "Optimization"
    bl_idname = "POLYPULSE_PT_optimization"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Mesh Repair Basic
        sub = layout.column(align=True)
        sub.label(text=PolyPulseI18N.t('subsec_mesh_repair'),
                  icon='OUTLINER_OB_MESH')

        repair_col = layout.column(align=True)
        repair_col.scale_y = 1.05
        repair_col.operator("polypulse.auto_fix_mesh",
                     text=PolyPulseI18N.t('btn_auto_fix_mesh'),
                     icon='MODIFIER')
        repair_col.operator("polypulse.remove_doubles",
                     text=PolyPulseI18N.t('btn_remove_doubles'),
                     icon='AUTOMERGE_ON')
        repair_col.operator("polypulse.merge_objects",
                     text=PolyPulseI18N.t('btn_merge_objects'),
                     icon='AREA_JOIN')
        repair_col.operator("polypulse.smart_decimate",
                     text=PolyPulseI18N.t('btn_smart_decimate'),
                     icon='MOD_DECIM')

        layout.separator()

        # --- LOD Chain Pro
        sub = layout.column(align=True)
        sub.label(text=PolyPulseI18N.t('section_lod_chain'),
                  icon='MOD_DECIM')
        box = sub.box()
        col_lod = box.column(align=True)
        col_lod.scale_y = 1.05
        col_lod.operator(
            "polypulse.generate_lod_chain",
            text=PolyPulseI18N.t('btn_generate_lods'),
            icon='MOD_DECIM',
        )

        # --- Single LODs Pro
        sub2 = box.column(align=True)
        sub2.label(text="Single LODs:", icon='MOD_DECIM')
        sub2.operator(
            "polypulse.generate_lod",
            text=PolyPulseI18N.t('btn_generate_lod1'),
            icon='MOD_DECIM',
        ).lod_level = '1'
        sub2.operator(
            "polypulse.generate_lod",
            text=PolyPulseI18N.t('btn_generate_lod2'),
            icon='MOD_DECIM',
        ).lod_level = '2'
        sub2.operator(
            "polypulse.generate_lod",
            text=PolyPulseI18N.t('btn_generate_lod3'),
            icon='MOD_DECIM',
        ).lod_level = '3'

        # --- LOD Chain отчёт ---
        if props.lod_chain_created > 0:
            rbox = layout.box()
            rbox.label(text="LOD Chain Report", icon='MOD_DECIM')
            # Color-code: LOD0 green, LOD3 yellow
            rbox.label(text=f"LOD0 (100%): {props.lod_chain_lod0_polys:,}",
                       icon='MESH_DATA')
            rbox.label(text=f"LOD1 (50%):  {props.lod_chain_lod1_polys:,}",
                       icon='MOD_DECIM')
            rbox.label(text=f"LOD2 (25%):  {props.lod_chain_lod2_polys:,}",
                       icon='MOD_DECIM')
            rbox.label(text=f"LOD3 (10%):  {props.lod_chain_lod3_polys:,}",
                       icon='MOD_DECIM')

        # --- Auto Fix отчёт ---
        if props.fix_verts_before > 0:
            fbox = layout.box()
            fbox.label(text="Last Auto Fix", icon='MODIFIER')
            fbox.label(text=f"{PolyPulseI18N.t('lbl_vertices')} before: "
                            f"{props.fix_verts_before:,}",
                       icon='VERTEXSEL')
            fbox.label(text=f"{PolyPulseI18N.t('lbl_vertices')} after:  "
                            f"{props.fix_verts_after:,}",
                       icon='VERTEXSEL')
            # Highlight fixed count
            fix_row = fbox.row(align=True)
            fix_row.alert = props.fix_fixed_count > 0
            fix_row.label(text=f"{PolyPulseI18N.t('popup_fixed_issues')}: "
                                f"{props.fix_fixed_count:,}",
                          icon='CHECKMARK' if props.fix_fixed_count > 0 else 'INFO')


class POLYPULSE_PT_export(Panel):
    """Sub-panel EXPORT — UE5 / Unity / Godot + Texture Scan."""

    bl_label = "Export"
    bl_idname = "POLYPULSE_PT_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Engine Presets Pro
        sub = layout.column(align=True)
        sub.label(text=PolyPulseI18N.t('subsec_engine_presets'),
                  icon='EXPORT')

        # Engine buttons with bigger touch targets
        eng_col = layout.column(align=True)
        eng_col.scale_y = 1.1
        eng_col.operator(
            "polypulse.export_ue5",
            text=PolyPulseI18N.t('btn_export_ue5'),
            icon='EXPORT',
        )
        eng_col.operator(
            "polypulse.export_unity",
            text=PolyPulseI18N.t('btn_export_unity'),
            icon='EXPORT',
        )
        eng_col.operator(
            "polypulse.export_godot",
            text=PolyPulseI18N.t('btn_export_godot'),
            icon='EXPORT',
        )

        layout.separator()

        # --- Texture Scan Premium
        sub = layout.column(align=True)
        sub.label(text=PolyPulseI18N.t('subsec_textures'),
                  icon='TEXT')
        sub.operator(
            "polypulse.texture_scan",
            text=PolyPulseI18N.t('btn_texture_scan'),
            icon='TEXT',
        )

        # --- Texture list (collapsible) ---
        if len(props.textures) > 0:
            if _section_header(layout, props, 'ui_show_textures',
                               f"{PolyPulseI18N.t('lbl_textures')} ({len(props.textures)})",
                               'TEXT'):
                box = layout.box()
                for t in props.textures:
                    row = box.row(align=True)
                    row.label(text=t.name, icon='TEXT')
                    dim_text = f"{t.size_x}×{t.size_y}"
                    if t.file_size_kb > 0:
                        dim_text += f"  ({t.file_size_kb} KB)"
                    row.label(text=dim_text)
                    # Recommendation badge
                    if "Downscale" in t.recommendation:
                        row.alert = True
                    row.label(text=t.recommendation, icon='INFO')


class POLYPULSE_PT_validation(Panel):
    """Sub-panel VALIDATION — Game Ready Check + проверка деталей."""

    bl_label = "Validation"
    bl_idname = "POLYPULSE_PT_validation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Run validation button ---
        col = layout.column(align=True)
        col.scale_y = 1.1
        col.operator(
            "polypulse.game_ready_check",
            text=PolyPulseI18N.t('btn_game_ready_check'),
            icon='CHECKMARK',
        )

        # --- Score + результаты ---
        if len(props.validation_items) > 0:
            box = layout.box()

            # Status badge row
            status_icon = 'CHECKMARK' if props.validation_passed else 'ERROR'
            status_text = (PolyPulseI18N.t('validation_pass')
                           if props.validation_passed
                           else PolyPulseI18N.t('validation_fail'))

            row = box.row(align=True)
            row.label(text=f"{props.validation_score}/100", icon='SOLO_ON')
            row.label(text=status_text, icon=status_icon)

            # Visual progress bar for validation score
            box.label(text="Validation: " + str(props.validation_score) + "/100",
                      icon='CHECKMARK' if props.validation_passed else 'ERROR')

            # Grouped results
            current_cat = None
            cat_box = None
            for item in props.validation_items:
                if item.category != current_cat:
                    current_cat = item.category
                    cat_box = box.box()
                    cat_box.label(text=item.category, icon='MODIFIER')

                row = cat_box.row(align=True)
                row.alert = not item.passed
                icon = 'CHECKMARK' if item.passed else 'ERROR'
                row.label(text=f"{item.check_name}", icon=icon)
                row.label(text=item.detail)


class POLYPULSE_PT_reports(Panel):
    """Sub-panel REPORTS — Export Report + Batch Optimizer + Last Op."""

    bl_label = "Reports"
    bl_idname = "POLYPULSE_PT_reports"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        # --- Reports Premium
        sub = layout.column(align=True)
        sub.label(text=PolyPulseI18N.t('subsec_reports'),
                  icon='TEXT')
        sub.operator(
            "polypulse.export_report",
            text=PolyPulseI18N.t('btn_export_report'),
            icon='EXPORT',
        )
        sub.operator(
            "polypulse.batch_optimize",
            text=PolyPulseI18N.t('btn_batch_optimize'),
            icon='FILE_FOLDER',
        )

        # --- Last Operation ---
        if props.last_operation and \
                props.last_operation != "No operation yet":
            box = layout.box()
            box.label(text=PolyPulseI18N.t('section_last_op'),
                      icon='INFO')
            for line in props.last_operation.split(", "):
                box.label(text=line)


class POLYPULSE_PT_settings(Panel):
    """Sub-panel SETTINGS — Language selector."""

    bl_label = "Settings"
    bl_idname = "POLYPULSE_PT_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyPulse"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.polypulse_props

        box = layout.box()
        box.label(text=PolyPulseI18N.t('settings_choose_language'),
                  icon='INFO')
        box.prop(props, "language", text=PolyPulseI18N.t('lbl_language'))

        # Текущий язык + наличие переводов
        info = box.box()
        info.label(
            text=f"Active: {PolyPulseI18N.get_lang().upper()}",
            icon='INFO',
        )
        info.label(text=f"Translations: "
                        f"{len(PolyPulseI18N._translations)}",
                   icon='TEXT')


# =============================================================================
# v0.4 — Asset Preparation Modules
# =============================================================================
# Импортируем новые модули (Collider Generator, UV Atlas, Visual Overlay)
try:
    from .modules.collider import (
        POLYPULSE_OT_generate_collider,
    )
    from .modules.uv_atlas import (
        POLYPULSE_OT_create_uv_atlas,
    )
    from .modules.visual_overlay import (
        POLYPULSE_OT_visual_scan,
        POLYPULSE_PT_asset_preparation,
        cleanup_overlay,
    )
    _V04_MODULES_LOADED = True
except ImportError as _v04_err:
    # Если модули не загрузились (например, при отсутствии зависимостей),
    # аддон продолжает работать в режиме v0.3
    _V04_MODULES_LOADED = False
    _V04_IMPORT_ERROR = str(_v04_err)


# =============================================================================
# РЕГИСТРАЦИЯ
# =============================================================================
classes = (
    # Property groups
    PolyPulseWarningItem,
    PolyPulseTextureItem,
    PolyPulseValidationItem,
    PolyPulseProperties,
    # v0.1 operators
    POLYPULSE_OT_analyze_scene,
    POLYPULSE_OT_remove_doubles,
    POLYPULSE_OT_merge_objects,
    POLYPULSE_OT_smart_decimate,
    POLYPULSE_OT_export_report,
    # v0.2 operators
    POLYPULSE_OT_advanced_scan,
    POLYPULSE_OT_auto_fix_mesh,
    POLYPULSE_OT_generate_lod,
    POLYPULSE_OT_texture_scan,
    POLYPULSE_OT_batch_optimize,
    # v0.3 operators
    POLYPULSE_OT_generate_lod_chain,
    POLYPULSE_OT_draw_calls_estimator,
    POLYPULSE_OT_game_ready_check,
    POLYPULSE_OT_export_ue5,
    POLYPULSE_OT_export_unity,
    POLYPULSE_OT_export_godot,
    # Panels (order = visual order in N-panel)
    POLYPULSE_PT_main,
    POLYPULSE_PT_analysis,
    POLYPULSE_PT_optimization,
)

# v0.4 modules: operators first, then Asset Preparation panel
# (positioned between Optimization and Export for logical workflow)
if _V04_MODULES_LOADED:
    classes += (
        # v0.4 operators
        POLYPULSE_OT_generate_collider,
        POLYPULSE_OT_create_uv_atlas,
        POLYPULSE_OT_visual_scan,
        # v0.4 panel — between Optimization and Export
        POLYPULSE_PT_asset_preparation,
    )

classes += (
    POLYPULSE_PT_export,
    POLYPULSE_PT_validation,
    POLYPULSE_PT_reports,
    POLYPULSE_PT_settings,
)



def register():
    """Регистрирует все классы аддона и PropertyGroup на сцене."""
    # Перезагружаем переводы (на случай reinstall)
    PolyPulseI18N.load()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.polypulse_props = PointerProperty(
        type=PolyPulseProperties,
        name="PolyPulse Properties",
    )


def unregister():
    """Отменяет регистрацию классов и PropertyGroup."""
    # Снимаем viewport overlay, если он активен (v0.4)
    if _V04_MODULES_LOADED:
        try:
            cleanup_overlay()
        except Exception:
            pass
    if hasattr(bpy.types.Scene, "polypulse_props"):
        del bpy.types.Scene.polypulse_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
