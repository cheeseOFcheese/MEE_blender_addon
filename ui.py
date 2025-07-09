"""
# MIT License
# Copyright (c) 2025 MEE_blender_addon
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

Пользовательский интерфейс для аддона неиспользуемых узлов.
"""

import bpy
from bpy.types import Panel, Context
from bpy.props import StringProperty


# ============================================================================
# СВОЙСТВА СЦЕНЫ
# ============================================================================

def register_scene_properties() -> None:
    """Зарегистрировать свойства сцены для аддона."""
    bpy.types.Scene.unused_nodes_attr_text = StringProperty(
        name="Текст атрибута",
        description="Текст для атрибута, который будет добавлен к неиспользуемым узлам",
        default="unused",
        maxlen=1024
    )
    
    bpy.types.Scene.unused_nodes_attr_type = bpy.props.EnumProperty(
        name="Тип атрибута",
        description="Тип атрибута для создания",
        items=[
            ('GEOMETRY', "Geometry", "Атрибут в геометрии"),
            ('OBJECT', "Object", "Атрибут в свойствах объекта"),
            ('INSTANCER', "Instancer", "Атрибут у инстансера"),
            ('VIEW_LAYER', "View Layer", "Атрибут из View Layer"),
        ],
        default='GEOMETRY'
    )
    
    bpy.types.Scene.unused_nodes_attr_channel = bpy.props.EnumProperty(
        name="Канал данных",
        description="Канал данных атрибута для подключения",
        items=[
            ('Color', "Color", "Цветовой канал"),
            ('Vector', "Vector", "Векторный канал"),
            ('Fac', "Fac", "Фактор"),
            ('Alpha', "Alpha", "Альфа-канал"),
        ],
        default='Color'
    )
    
    bpy.types.Scene.unused_nodes_show_attributes = bpy.props.BoolProperty(
        name="Показывать в отчёте атрибуты",
        description="Включить отображение атрибутов в отчете о неиспользуемых узлах",
        default=True
    )


def unregister_scene_properties() -> None:
    """Отменить регистрацию свойств сцены."""
    del bpy.types.Scene.unused_nodes_attr_text
    del bpy.types.Scene.unused_nodes_attr_type
    del bpy.types.Scene.unused_nodes_attr_channel
    del bpy.types.Scene.unused_nodes_show_attributes


# ============================================================================
# ПАНЕЛИ
# ============================================================================

class NODE_PT_unused_nodes(Panel):
    """Панель для работы с неиспользуемыми узлами в редакторе узлов."""
    
    bl_label = "Неиспользуемые узлы"
    bl_idname = "NODE_PT_unused_nodes"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Unused'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        """Проверить, должна ли панель отображаться.
        
        Args:
            context: Контекст Blender
            
        Returns:
            bool: True если панель должна отображаться
        """
        return context.space_data is not None

    def draw(self, context: Context) -> None:
        """Отрисовать содержимое панели.
        
        Args:
            context: Контекст Blender
        """
        layout = self.layout
        
        # Секция настроек
        box = layout.box()
        box.label(text="Настройки")
        
        row = box.row()
        row.prop(context.scene, "unused_nodes_attr_text", text="Атрибут")
        
        row = box.row()
        row.prop(context.scene, "unused_nodes_attr_type", text="Тип атрибута")
        
        row = box.row()
        row.prop(context.scene, "unused_nodes_attr_channel", text="Канал данных")
        
        row = box.row()
        row.prop(context.scene, "unused_nodes_show_attributes", text="Показывать в отчёте атрибуты")
        
        layout.separator()
        
        # Секция отчетов
        box = layout.box()
        box.label(text="Отчеты")
        
        row = box.row()
        row.scale_y = 1.2
        row.operator(
            "node.find_unused_nodes_popup",
            text="Создать расширенный отчет"
        )
        
        layout.separator()
        
        # Секция группировки
        box = layout.box()
        box.label(text="Группировка")
        
        col = box.column(align=True)
        col.operator(
            "node.group_unused_nodes_active",
            text="Группировать в активном дереве"
        )
        col.operator(
            "node.group_unused_nodes_all",
            text="Группировать во всех материалах"
        )
        
        layout.separator()
        
        # Секция удаления
        box = layout.box()
        box.label(text="Удаление")
        
        col = box.column(align=True)
        col.operator(
            "node.delete_unused_nodes",
            text="Удалить в активном дереве"
        )
        col.operator(
            "node.delete_all_unused_nodes",
            text="Удалить во всех материалах"
        )


# ============================================================================
# РЕГИСТРАЦИЯ
# ============================================================================

classes = [
    NODE_PT_unused_nodes
]


def register() -> None:
    """Зарегистрировать все классы UI."""
    for cls in classes:
        bpy.utils.register_class(cls)
    register_scene_properties()


def unregister() -> None:
    """Отменить регистрацию всех классов UI."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_scene_properties() 