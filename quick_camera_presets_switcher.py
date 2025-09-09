bl_info = {
    "name": "Quick Camera Presets Switcher",
    "author": "Nan Kang",
    "version": (1, 0, 1),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Quick Cam",
    "description": "One‑click camera presets with optional aim‑at‑active.",
    "category": "3D View",
}

import math
import bpy
from mathutils import Vector, Matrix

# --- Presets (simple dicts to keep it obvious) ---
PRESETS = (
    {
        "name": "35mm Medium",
        "type": "PERSP",
        "lens": 35.0,
        "loc": (0.0, -6.0, 3.0),
        "rot_deg": (60.0, 0.0, 0.0),
    },
    {
        "name": "50mm Portrait",
        "type": "PERSP",
        "lens": 50.0,
        "loc": (0.0, -4.0, 1.8),
        "rot_deg": (65.0, 0.0, 0.0),
    },
    {
        "name": "85mm Close‑Up",
        "type": "PERSP",
        "lens": 85.0,
        "loc": (0.0, -3.0, 1.6),
        "rot_deg": (70.0, 0.0, 0.0),
    },
    {
        "name": "Isometric (Ortho)",
        "type": "ORTHO",
        "ortho": 10.0,
        "loc": (10.0, -10.0, 10.0),
        "rot_deg": (35.264, 0.0, 45.0),
    },
    {
        "name": "Top Down (Ortho)",
        "type": "ORTHO",
        "ortho": 12.0,
        "loc": (0.0, 0.0, 20.0),
        "rot_deg": (90.0, 0.0, 0.0),
    },
)

PRESET_ITEMS = [(str(i), p["name"], "") for i, p in enumerate(PRESETS)]


# --- Helpers ---

def get_scene_cam(context):
    cam = context.scene.camera
    if cam and cam.type == 'CAMERA':
        return cam
    data = bpy.data.cameras.new("QuickCam")
    obj = bpy.data.objects.new("QuickCam", data)
    context.scene.collection.objects.link(obj)
    context.scene.camera = obj
    return obj


def aim_at(obj, target_co):
    d = (target_co - obj.location).normalized()
    z = -d
    up = Vector((0.0, 0.0, 1.0))
    x = up.cross(z).normalized()
    y = z.cross(x).normalized()
    obj.rotation_euler = Matrix((x, y, z)).transposed().to_euler()


def apply_preset(context, idx, aim_active, keep_loc):
    p = PRESETS[idx]
    cam = get_scene_cam(context)
    cam_data = cam.data

    cam_data.type = p["type"]
    if cam_data.type == 'PERSP':
        cam_data.lens = float(p.get("lens", cam_data.lens))
    else:
        cam_data.ortho_scale = float(p.get("ortho", cam_data.ortho_scale))

    if not keep_loc:
        cam.location = Vector(p["loc"]) 

    if aim_active and context.active_object is not None:
        aim_at(cam, context.active_object.matrix_world.translation)
    else:
        rx, ry, rz = (math.radians(a) for a in p["rot_deg"])
        cam.rotation_euler = (rx, ry, rz)


# --- Properties ---
class QCP_Saved(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Preset")
    type: bpy.props.EnumProperty(name="Type", items=[('PERSP','PERSP',''),('ORTHO','ORTHO','')], default='PERSP')
    lens: bpy.props.FloatProperty(name="Lens (mm)", default=50.0, min=1.0, soft_max=300.0)
    ortho: bpy.props.FloatProperty(name="Ortho Scale", default=10.0, min=0.001, soft_max=1000.0)
    loc: bpy.props.FloatVectorProperty(name="Location", size=3, default=(0.0,0.0,0.0))
    rot_deg: bpy.props.FloatVectorProperty(name="Rotation (deg)", size=3, default=(0.0,0.0,0.0))


class QCP_Props(bpy.types.PropertyGroup):
    preset: bpy.props.EnumProperty(name="Preset", items=PRESET_ITEMS, default='0')
    aim_active: bpy.props.BoolProperty(name="Aim at Active", default=True)
    keep_loc: bpy.props.BoolProperty(name="Keep Location", default=False)

    saved: bpy.props.CollectionProperty(type=QCP_Saved)
    saved_index: bpy.props.IntProperty()


# --- Operator ---
class QCP_OT_Apply(bpy.types.Operator):
    bl_idname = "qcp.apply_preset"
    bl_label = "Apply Camera Preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.qcp
        try:
            apply_preset(context, int(s.preset), s.aim_active, s.keep_loc)
        except Exception as e:
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class QCP_OT_SavedAddCurrent(bpy.types.Operator):
    bl_idname = "qcp.saved_add_current"
    bl_label = "Add Current Camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.qcp
        cam = context.scene.camera
        if not cam or cam.type != 'CAMERA':
            self.report({'ERROR'}, "No scene camera to save.")
            return {'CANCELLED'}
        item = s.saved.add()
        item.name = f"Preset {len(s.saved):03d}"
        item.type = cam.data.type
        if item.type == 'PERSP':
            item.lens = cam.data.lens
        else:
            item.ortho = cam.data.ortho_scale
        item.loc = cam.location
        # Store rotation in degrees for readability
        item.rot_deg = tuple(math.degrees(a) for a in cam.rotation_euler)
        s.saved_index = len(s.saved) - 1
        return {'FINISHED'}


class QCP_OT_SavedApply(bpy.types.Operator):
    bl_idname = "qcp.saved_apply"
    bl_label = "Apply Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.qcp
        i = s.saved_index
        if not (0 <= i < len(s.saved)):
            self.report({'ERROR'}, "No preset selected.")
            return {'CANCELLED'}
        it = s.saved[i]
        cam = get_scene_cam(context)
        cam.data.type = it.type
        if it.type == 'PERSP':
            cam.data.lens = it.lens
        else:
            cam.data.ortho_scale = it.ortho
        cam.location = it.loc
        rx, ry, rz = (math.radians(a) for a in it.rot_deg)
        cam.rotation_euler = (rx, ry, rz)
        return {'FINISHED'}


class QCP_OT_SavedRemove(bpy.types.Operator):
    bl_idname = "qcp.saved_remove"
    bl_label = "Remove Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.qcp
        i = s.saved_index
        if not (0 <= i < len(s.saved)):
            self.report({'ERROR'}, "No preset selected.")
            return {'CANCELLED'}
        s.saved.remove(i)
        s.saved_index = min(i, len(s.saved) - 1)
        return {'FINISHED'}


class QCP_OT_SavedUpdateFromCurrent(bpy.types.Operator):
    bl_idname = "qcp.saved_update_from_current"
    bl_label = "Capture From Current"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.qcp
        i = s.saved_index
        cam = context.scene.camera
        if not cam or cam.type != 'CAMERA' or not (0 <= i < len(s.saved)):
            self.report({'ERROR'}, "Need a scene camera and a selected preset.")
            return {'CANCELLED'}
        it = s.saved[i]
        it.type = cam.data.type
        if it.type == 'PERSP':
            it.lens = cam.data.lens
        else:
            it.ortho = cam.data.ortho_scale
        it.loc = cam.location
        it.rot_deg = tuple(math.degrees(a) for a in cam.rotation_euler)
        return {'FINISHED'}


# --- UI ---
class QCP_UL_Saved(bpy.types.UIList):
    bl_idname = "QCP_UL_saved"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # item is QCP_Saved
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False)
            row.label(text=item.type)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="")


class QCP_PT_Panel(bpy.types.Panel):
    bl_idname = "QCP_PT_panel"
    bl_label = "Quick Cam"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Quick Cam'

    def draw(self, context):
        layout = self.layout
        s = context.scene.qcp

        box = layout.box()
        box.label(text="Built-in Presets")
        col = box.column(align=True)
        col.prop(s, "preset")
        col.prop(s, "aim_active")
        col.prop(s, "keep_loc")
        col.operator("qcp.apply_preset", icon='OUTLINER_OB_CAMERA')

        layout.separator()

        box2 = layout.box()
        box2.label(text="Custom Presets (saved in .blend)")
        row = box2.row()
        row.template_list("QCP_UL_saved", "", s, "saved", s, "saved_index", rows=4)
        col_btns = row.column(align=True)
        col_btns.operator("qcp.saved_add_current", text="Add", icon='ADD')
        col_btns.operator("qcp.saved_remove", text="Remove", icon='REMOVE')
        col_btns.separator()
        col_btns.operator("qcp.saved_update_from_current", text="Overwrite", icon='FILE_REFRESH')
        col_btns.separator()
        col_btns.operator("qcp.saved_apply", text="Apply", icon='RESTRICT_RENDER_OFF')

        if 0 <= s.saved_index < len(s.saved):
            item = s.saved[s.saved_index]
            # Only allow renaming; capture numerics from the current camera via buttons
        col = box2.column(align=True)
        if 0 <= s.saved_index < len(s.saved):
            item = s.saved[s.saved_index]
            col.prop(item, "name", text="Preset Name")
            help_box = col.box()
            help_box.label(text="Numbers are captured from the current camera.")
            help_box.label(text="Use Add or Overwrite to update values.")


# --- Register ---
CLASSES = (
    QCP_Saved,
    QCP_Props,
    QCP_OT_Apply,
    QCP_OT_SavedAddCurrent,
    QCP_OT_SavedApply,
    QCP_OT_SavedRemove,
    QCP_OT_SavedUpdateFromCurrent,
    QCP_UL_Saved,
    QCP_PT_Panel,
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.qcp = bpy.props.PointerProperty(type=QCP_Props)


def unregister():
    del bpy.types.Scene.qcp
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
