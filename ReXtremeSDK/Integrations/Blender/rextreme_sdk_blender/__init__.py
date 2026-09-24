bl_info = {
    "name": "ReXtreme SDK Blender Tools",
    "author": "ReXtreme Project",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > ReXtreme",
    "description": "Prepare Blender scenes for ReXtreme SDK import",
    "category": "Import-Export",
}

import bpy
import json
from pathlib import Path

ROLE_ITEMS = [
    ("vehicle_body", "Vehicle Body", ""),
    ("wheel_fl", "Wheel FL", ""),
    ("wheel_fr", "Wheel FR", ""),
    ("wheel_rl", "Wheel RL", ""),
    ("wheel_rr", "Wheel RR", ""),
    ("collision", "Collision", ""),
    ("track_geometry", "Track Geometry", ""),
    ("start", "Start", ""),
    ("finish", "Finish", ""),
    ("checkpoint", "Checkpoint", ""),
    ("respawn", "Respawn", ""),
    ("ai_route", "AI Route", ""),
    ("replay_camera", "Replay Camera", ""),
    ("audio_zone", "Audio Zone", ""),
    ("prop", "Prop", ""),
]

class REXTREME_Props(bpy.types.PropertyGroup):
    role: bpy.props.EnumProperty(name="Role", items=ROLE_ITEMS)
    marker_id: bpy.props.StringProperty(name="Marker ID", default="")

class REXTREME_OT_mark_selected(bpy.types.Operator):
    bl_idname = "rextreme.mark_selected"
    bl_label = "Apply Role"
    bl_description = "Apply the selected ReXtreme role to selected Blender objects"

    def execute(self, context):
        role = context.scene.rextreme_sdk.role
        marker = context.scene.rextreme_sdk.marker_id.strip()
        for obj in context.selected_objects:
            obj["rx_role"] = role
            if marker:
                obj["rx_id"] = marker
        self.report({"INFO"}, f"Marked {len(context.selected_objects)} object(s) as {role}")
        return {"FINISHED"}

class REXTREME_OT_export_bundle(bpy.types.Operator):
    bl_idname = "rextreme.export_bundle"
    bl_label = "Export ReXtreme Bundle"
    bl_description = "Export a GLB plus ReXtreme metadata JSON for the SDK"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        target = Path(self.filepath)
        if target.suffix.lower() != ".glb":
            target = target.with_suffix(".glb")
        target.parent.mkdir(parents=True, exist_ok=True)

        objects = []
        for obj in context.scene.objects:
            custom = {str(k): obj[k] for k in obj.keys() if str(k).startswith("rx_")}
            objects.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation_euler": list(obj.rotation_euler),
                "scale": list(obj.scale),
                "rextreme": custom,
            })

        bpy.ops.export_scene.gltf(
            filepath=str(target),
            export_format="GLB",
            export_apply=True,
            export_yup=True,
        )

        metadata = {
            "schema_version": 1,
            "source": bpy.data.filepath,
            "glb": target.name,
            "objects": objects,
        }
        target.with_suffix(".rxscene.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.report({"INFO"}, f"Exported {target.name}")
        return {"FINISHED"}

    def invoke(self, context, event):
        base = Path(bpy.data.filepath).stem if bpy.data.filepath else "rextreme_scene"
        self.filepath = base + ".glb"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

class REXTREME_PT_tools(bpy.types.Panel):
    bl_label = "ReXtreme SDK"
    bl_idname = "REXTREME_PT_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ReXtreme"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rextreme_sdk
        layout.label(text="Object / Marker Role")
        layout.prop(props, "role")
        layout.prop(props, "marker_id")
        layout.operator("rextreme.mark_selected", icon="BOOKMARKS")
        layout.separator()
        layout.label(text="SDK Interchange")
        layout.operator("rextreme.export_bundle", icon="EXPORT")
        layout.separator()
        layout.label(text="Use GLB + .rxscene.json in ReXtreme SDK")

CLASSES = (
    REXTREME_Props,
    REXTREME_OT_mark_selected,
    REXTREME_OT_export_bundle,
    REXTREME_PT_tools,
)

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rextreme_sdk = bpy.props.PointerProperty(type=REXTREME_Props)

def unregister():
    del bpy.types.Scene.rextreme_sdk
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
