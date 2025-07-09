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

Операторы для аддона неиспользуемых узлов.
"""

import bpy
import logging
import os
import sys
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Set
from bpy.types import (
    Operator, 
    Material, 
    Node, 
    NodeTree, 
    NodeFrame, 
    Context,
    Window,
    Screen,
    Area,
    Region,
    SpaceTextEditor,
    SpaceConsole
)
from bpy.props import StringProperty, IntProperty

# Импорт утилит
from .utils import (
    get_output_nodes, 
    find_unused_nodes_recursive,
    collect_group_usage,
    layout_nodes_grid,
    place_group_left_of_used,
    remove_tmp_attribute_nodes
)

# Настройка логирования
logger = logging.getLogger(__name__)


class ReportManager:
    """Менеджер для создания и управления отчетами."""
    
    @staticmethod
    def build_report(show_attributes: bool = True) -> Tuple[str, str, str]:
        """Построить подробный отчет о неиспользуемых узлах.
        
        Args:
            show_attributes: Показывать ли атрибуты в отчете
            
        Returns:
            Tuple[str, str, str]: (report_text, text_name, file_path)
        """
        # Получаем все материалы
        materials = [mat for mat in bpy.data.materials if mat and mat.use_nodes and mat.node_tree]
        
        if not materials:
            report_lines = [
                "ОТЧЁТ О НЕИСПОЛЬЗУЕМЫХ УЗЛАХ",
                f"Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                "Нет материалов для анализа.",
                "=" * 60
            ]
            report_text = "\n".join(report_lines)
            text_name = f"unused_nodes_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            
            # Создаем текстовый блок
            text_block = bpy.data.texts.new(text_name)
            text_block.write(report_text)
            
            # Сохраняем на диск
            report_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "reports")
            os.makedirs(report_dir, exist_ok=True)
            file_path = os.path.join(report_dir, f"{text_name}.txt")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_text)
            
            return report_text, text_name, file_path
        
        # Собираем все неиспользуемые узлы из всех материалов
        all_unused_dict: Dict[Node, Dict] = {}
        
        for material in materials:
            if material.node_tree:
                # Рекурсивно находим неиспользуемые узлы в материале
                material_unused = find_unused_nodes_recursive(material.node_tree, material.name, show_attributes)
                all_unused_dict.update(material_unused)
        
        # Собираем информацию о группах
        collect_group_usage(all_unused_dict, materials)
        
        # Формируем отчет
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines = [
            "ОТЧЁТ О НЕИСПОЛЬЗУЕМЫХ УЗЛАХ",
            f"Создан: {timestamp}",
            f"Проанализировано материалов: {len(materials)}",
            "=" * 60
        ]
        
        if not all_unused_dict:
            report_lines.append("Все ноды используются.")
        else:
            # Выводим информацию о каждой неиспользуемой ноде
            for node, info in all_unused_dict.items():
                line = f"[{info['parent_tree']}] {node.name} ({info['type']})"
                report_lines.append(line)
                
                # Если это группа и есть материалы, где она используется
                if info["type"] == "GROUP" and info["materials"]:
                    mats = ", ".join(info["materials"])
                    report_lines.append(f"  → Группа используется в материалах: [{mats}]")
                    
                    # Показываем информацию о подключении к выходу
                    if info.get("connected_to_output"):
                        connected_mats = ", ".join(info["connected_to_output"])
                        report_lines.append(f"  → Подключена к выходу в материалах: [{connected_mats}]")
                    else:
                        report_lines.append(f"  → НЕ подключена к выходу ни в одном материале")
            
            report_lines.append(f"\nВсего найдено неиспользуемых узлов: {len(all_unused_dict)}")
        
        report_lines.append("=" * 60)
        
        report_text = "\n".join(report_lines)
        text_name = f"unused_nodes_report_{timestamp.replace(':', '-').replace(' ', '_')}"
        
        # Создаем текстовый блок
        text_block = bpy.data.texts.new(text_name)
        text_block.write(report_text)
        
        # Сохраняем на диск
        report_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "reports")
        os.makedirs(report_dir, exist_ok=True)
        file_path = os.path.join(report_dir, f"{text_name}.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        
        # Выводим в консоль
        print("\n" + "=" * 60, file=sys.stdout)
        print("ОТЧЕТ О НЕИСПОЛЬЗУЕМЫХ УЗЛАХ", file=sys.stdout)
        print("=" * 60, file=sys.stdout)
        for line in report_lines:
            print(line, file=sys.stdout)
        print("=" * 60, file=sys.stdout)
        
        return report_text, text_name, file_path





class NodeTreeProcessor:
    """Базовый класс для обработки деревьев узлов."""
    
    @staticmethod
    def get_active_node_tree(context: Context) -> Optional[NodeTree]:
        """Получить активное дерево узлов.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Optional[NodeTree]: Активное дерево узлов или None
        """
        if not context.space_data:
            return None
        return context.space_data.node_tree
    
    @staticmethod
    def validate_node_tree(tree: Optional[NodeTree], operator: Operator) -> bool:
        """Проверить валидность дерева узлов.
        
        Args:
            tree: Дерево узлов для проверки
            operator: Оператор для отправки сообщений
            
        Returns:
            bool: True если дерево валидно, False иначе
        """
        if not tree:
            operator.report({'WARNING'}, "Нет активного дерева узлов")
            return False
        return True


# ============================================================================
# ОПЕРАТОРЫ УДАЛЕНИЯ
# ============================================================================

class NODE_OT_DeleteUnusedNodes(Operator):
    """Удалить неиспользуемые узлы в активном дереве узлов."""
    
    bl_idname = "node.delete_unused_nodes"
    bl_label = "Удалить неиспользуемые (активное дерево)"
    bl_description = "Удалить все неиспользуемые узлы в активном дереве узлов"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        """Выполнить удаление неиспользуемых узлов в активном дереве.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            tree = NodeTreeProcessor.get_active_node_tree(context)
            if not NodeTreeProcessor.validate_node_tree(tree, self):
                return {'CANCELLED'}
            
            unused_dict = find_unused_nodes_recursive(tree)
            
            if not unused_dict:
                self.report({'INFO'}, "Неиспользуемых узлов не найдено")
                return {'FINISHED'}

            for node in unused_dict.keys():
                tree.nodes.remove(node)
            
            self.report({'INFO'}, f"Удалено {len(unused_dict)} неиспользуемых узлов")
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при удалении неиспользуемых узлов: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при удалении: {str(e)}")
            return {'CANCELLED'}


class NODE_OT_DeleteAllUnusedNodes(Operator):
    """Удалить неиспользуемые узлы во всех материалах сцены."""
    
    bl_idname = "node.delete_all_unused_nodes"
    bl_label = "Удалить все неиспользуемые (все деревья)"
    bl_description = "Удалить неиспользуемые узлы во всех материалах сцены"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        """Выполнить удаление неиспользуемых узлов во всех материалах.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            total_deleted = 0
            materials_processed = 0
            
            for material in bpy.data.materials:
                if material and material.use_nodes and material.node_tree:
                    unused_dict = find_unused_nodes_recursive(material.node_tree)
                    if unused_dict:
                        for node in unused_dict.keys():
                            material.node_tree.nodes.remove(node)
                        total_deleted += len(unused_dict)
                    materials_processed += 1
            
            if total_deleted == 0:
                self.report({'INFO'}, "Неиспользуемых узлов не найдено")
            else:
                self.report({'INFO'}, f"Удалено {total_deleted} неиспользуемых узлов из {materials_processed} материалов")
            
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при удалении всех неиспользуемых узлов: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при удалении: {str(e)}")
            return {'CANCELLED'}


# ============================================================================
# ОПЕРАТОРЫ ОТЧЕТОВ
# ============================================================================

class NODE_OT_SimpleReportPopup(Operator):
    """Упрощенный квадратный попап с отчетом о неиспользуемых узлах."""
    
    bl_idname = "node.simple_report_popup"
    bl_label = "Отчёт"
    bl_options = {'INTERNAL'}

    report_text: StringProperty()
    text_name: StringProperty()
    file_path: StringProperty()

    def invoke(self, context: Context, event) -> Set[str]:
        """Вызвать попап с фиксированной шириной.
        
        Args:
            context: Контекст Blender
            event: Событие
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        return context.window_manager.invoke_popup(self, width=200)

    def draw(self, context: Context) -> None:
        """Отрисовать содержимое упрощенного попапа.
        
        Args:
            context: Контекст Blender
        """
        layout = self.layout
        
        # Извлекаем статистику из отчета
        lines = self.report_text.split('\n')
        stats: Dict[str, str] = {}
        
        for line in lines:
            if "Проанализировано материалов:" in line:
                stats['materials'] = line.split(":")[1].strip()
            elif "Всего найдено неиспользуемых узлов:" in line:
                stats['unused'] = line.split(":")[1].strip()
            elif "неиспользуемых узлов не найдено" in line:
                stats['unused'] = "0"
            elif "Все ноды используются" in line:
                stats['unused'] = "0"
            elif "Нет материалов для анализа" in line:
                stats['materials'] = "0"
                stats['unused'] = "0"
        
        # Минималистичный дизайн
        layout.label(text="Отчет о нодах")
        
        if 'materials' in stats:
            layout.label(text=f"Материалов: {stats['materials']}")
        
        if 'unused' in stats:
            if stats['unused'] == "0":
                layout.label(text="Неиспользуемых: 0")
            else:
                layout.label(text=f"Неиспользуемых: {stats['unused']}")
        
        # Кнопка для открытия полного отчета
        op = layout.operator(
            "text.open_unused_nodes_report_window",
            text="Полный отчёт"
        )
        op.text_name = self.text_name
        op.file_path = self.file_path

    def execute(self, context: Context) -> Set[str]:
        """Выполнить оператор.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        return {'FINISHED'}


class NODE_OT_FindUnusedNodesPopup(Operator):
    """Создать подробный отчет о неиспользуемых узлах с всплывающим окном."""
    
    bl_idname = "node.find_unused_nodes_popup"
    bl_label = "Подробный отчет"
    bl_description = "Создать подробный отчет о неиспользуемых узлах"
    bl_options = {'REGISTER'}

    max_popup_lines: IntProperty(
        name="Максимум строк в всплывающем окне",
        description="Максимальное количество строк для отображения в всплывающем окне",
        default=20,
        min=5,
        max=50
    )

    def execute(self, context: Context) -> Set[str]:
        """Создать и показать подробный отчет.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            show_attributes = context.scene.unused_nodes_show_attributes
            report_text, text_name, file_path = ReportManager.build_report(show_attributes)
            
            # Используем новый упрощенный попап
            bpy.ops.node.simple_report_popup(
                'INVOKE_DEFAULT',
                report_text=report_text,
                text_name=text_name,
                file_path=file_path
            )
            
            self.report({'INFO'}, f"Отчет сохранен в текстовый блок '{text_name}'")
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при создании отчета: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при создании отчета: {str(e)}")
            return {'CANCELLED'}


class TEXT_OT_OpenUnusedNodesReport(Operator):
    """Открыть отчет о неиспользуемых узлах в редакторе текста."""
    
    bl_idname = "text.open_unused_nodes_report"
    bl_label = "Открыть отчет о неиспользуемых узлах"
    bl_description = "Открыть полный отчет в редакторе текста"

    text_name: StringProperty(
        name="Имя текстового блока",
        description="Имя текстового блока для открытия"
    )

    def execute(self, context: Context) -> Set[str]:
        """Открыть отчет в редакторе текста.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            text_block = bpy.data.texts.get(self.text_name)
            if not text_block:
                self.report({'ERROR'}, f"Текстовый блок '{self.text_name}' не найден")
                return {'CANCELLED'}
            
            if not context.area:
                self.report({'ERROR'}, "Нет активной области для разделения")
                return {'CANCELLED'}
            
            # Используем temp_override для корректной работы в Blender 4.4+
            with context.temp_override(area=context.area):
                bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
            context.area.ui_type = 'TEXT_EDITOR'
            context.area.spaces[0].text = text_block
            
            self.report({'INFO'}, "Отчет открыт в редакторе текста")
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при открытии отчета: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при открытии отчета: {str(e)}")
            return {'CANCELLED'}


class TEXT_OT_OpenUnusedNodesReportWindow(Operator):
    """Открыть отчет в отдельном плавающем окне (консоль + текст)."""

    bl_idname = "text.open_unused_nodes_report_window"
    bl_label = "Открыть отчет в окне"

    text_name: StringProperty()
    file_path: StringProperty()

    def execute(self, context: Context) -> Set[str]:
        """Открыть отчет в отдельном окне.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            # 1. Получаем текстовый блок
            text_block = bpy.data.texts.get(self.text_name)
            if not text_block:
                self.report({'ERROR'}, f"Блок '{self.text_name}' не найден")
                return {'CANCELLED'}

            # 2. Создаём плавающее окно
            bpy.ops.wm.window_new()
            win: Window = context.window_manager.windows[-1]

            # 3. Левая область — CONSOLE
            area: Area = win.screen.areas[0]
            area.type = 'CONSOLE'
            region: Region = next(r for r in area.regions if r.type == 'WINDOW')

            # Выводим заголовок отчета
            with context.temp_override(window=win, area=area, region=region):
                bpy.ops.console.scrollback_append(text="")
                bpy.ops.console.scrollback_append(text="=" * 60)
                bpy.ops.console.scrollback_append(text="ОТЧЕТ О НЕИСПОЛЬЗУЕМЫХ УЗЛАХ")
                bpy.ops.console.scrollback_append(text="=" * 60)
            
            # Выводим полный отчет в консоль с форматированием
            report_lines = text_block.as_string().split('\n')
            for line in report_lines:
                if line.strip():
                    # Определяем тип строки для правильного форматирования
                    if line.startswith('ОТЧЁТ О НЕИСПОЛЬЗУЕМЫХ УЗЛАХ'):
                        continue  # Пропускаем дублирующий заголовок
                    elif line.startswith('Создан:'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('Проанализировано материалов:'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('='):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('[') and ']' in line and '(' in line:
                        # Строка с информацией о ноде
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('  → Группа используется в материалах:'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('Всего найдено неиспользуемых узлов:'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('Все ноды используются'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    elif line.startswith('Нет материалов для анализа'):
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                    else:
                        with context.temp_override(window=win, area=area, region=region):
                            bpy.ops.console.scrollback_append(text=line)
                else:
                    with context.temp_override(window=win, area=area, region=region):
                        bpy.ops.console.scrollback_append(text="")
            
            # Добавляем информацию о сохранении
            with context.temp_override(window=win, area=area, region=region):
                bpy.ops.console.scrollback_append(text="")
                bpy.ops.console.scrollback_append(text="=" * 60)
                bpy.ops.console.scrollback_append(text="ИНФОРМАЦИЯ О СОХРАНЕНИИ:")
                bpy.ops.console.scrollback_append(text=f"Файл на диске: {os.path.relpath(self.file_path)}")
                bpy.ops.console.scrollback_append(text=f"Текстовый блок: {self.text_name}")
                bpy.ops.console.scrollback_append(text="=" * 60)

            # 4. Дробим окно пополам с правильным контекстом
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.5)

            # 5. Идентифицируем верхнюю и нижнюю области по Y координате
            areas = sorted(win.screen.areas, key=lambda a: a.y, reverse=True)
            top: Area = areas[0]  # Верхняя область (терминал)
            bottom: Area = areas[1]  # Нижняя область (текст)

            # 6. Настраиваем нижнюю область как TEXT_EDITOR
            bottom.type = 'TEXT_EDITOR'
            txt_space: SpaceTextEditor = bottom.spaces[0]
            txt_space.text = text_block
            txt_space.show_word_wrap = True

            # 7. Перемещаем курсор на первую строку текстового редактора
            txt_space.top = 0  # Прокручиваем к началу текста
            # В Blender 4.4+ select_set больше не существует, используем альтернативный способ
            try:
                # Пытаемся установить курсор через text_block
                if hasattr(text_block, 'current_line_index'):
                    text_block.current_line_index = 0
                if hasattr(text_block, 'current_character'):
                    text_block.current_character = 0
            except:
                # Если не удалось, просто прокручиваем к началу
                pass

            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при открытии отчета в окне: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при открытии отчета: {str(e)}")
            return {'CANCELLED'}


# ============================================================================
# ОПЕРАТОРЫ ГРУППИРОВКИ
# ============================================================================

class BaseGroupUnusedNodes:
    """Базовый класс для группировки неиспользуемых узлов."""
    
    def _remove_existing_unused_frame(self, node_tree: NodeTree) -> None:
        """Удалить существующий фрейм UNUSED_FRAME и все атрибуты в нем.
        
        Args:
            node_tree: Дерево узлов для очистки
        """
        existing_frame = None
        for node in node_tree.nodes:
            if node.type == 'FRAME' and node.name == "UNUSED_FRAME":
                existing_frame = node
                break
        
        if existing_frame:
            node_tree.nodes.remove(existing_frame)

    def _remove_old_attributes(self, node_tree: NodeTree) -> None:
        """Удалить все старые атрибуты из дерева узлов.
        
        Args:
            node_tree: Дерево узлов для очистки
        """
        remove_tmp_attribute_nodes(node_tree)

    def _add_attribute_node(self, node_tree: NodeTree, target_node: Node, attr_text: str, attr_type: str = 'GEOMETRY', attr_channel: str = 'Color') -> Optional[Node]:
        """Добавить Attribute-ноду к целевому узлу.
        
        Args:
            node_tree: Дерево узлов
            target_node: Целевой узел
            attr_text: Текст атрибута
            attr_type: Тип атрибута (GEOMETRY, OBJECT, INSTANCER, VIEW_LAYER)
            attr_channel: Канал данных атрибута (Color, Vector, Fac, Alpha)
            
        Returns:
            Optional[Node]: Созданная Attribute-нода или None
        """
        # Проверяем, есть ли у ноды входы и есть ли свободные входы
        if not target_node.inputs:
            return None  # У ноды нет входов вообще
        
        # Находим первый свободный входной сокет
        free_input = None
        for input_socket in target_node.inputs:
            if not input_socket.is_linked:
                free_input = input_socket
                break
        
        # Если нет свободных входов, не создаем атрибут
        if not free_input:
            return None
        
        # Определяем правильный тип ноды в зависимости от типа дерева
        if node_tree.type == 'SHADER':
            attr_node = node_tree.nodes.new(type='ShaderNodeAttribute')
        elif node_tree.type == 'GEOMETRY':
            attr_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        else:
            attr_node = node_tree.nodes.new(type='ShaderNodeAttribute')
        
        attr_node.name = f"Attr_{target_node.name}"
        attr_node.label = "_tmp_attr"  # Помечаем ноду для последующего удаления
        attr_node.attribute_name = attr_text
        
        # Устанавливаем тип атрибута для ShaderNodeAttribute
        if hasattr(attr_node, 'attribute_type'):
            attr_node.attribute_type = attr_type
        
        # Подключаем атрибут к свободному входу
        if attr_node.outputs:
            # Ищем выход с выбранным каналом
            output_socket = None
            for output in attr_node.outputs:
                if output.name == attr_channel:
                    output_socket = output
                    break
            
            # Если выбранный канал не найден, используем первый доступный
            if not output_socket:
                output_socket = attr_node.outputs[0]
            
            node_tree.links.new(output_socket, free_input)
        
        return attr_node

    def _create_unused_frame(self, node_tree: NodeTree, pairs: List[Tuple[Optional[Node], Node]]) -> None:
        """Создать фрейм с неиспользуемыми узлами используя улучшенную логику.
        
        Args:
            node_tree: Дерево узлов
            pairs: Список пар (attribute_node, target_node)
        """
        if not pairs:
            return
        
        # Собираем все узлы для размещения
        all_nodes: List[Node] = []
        for attr_node, target_node in pairs:
            if attr_node:
                all_nodes.append(attr_node)
            all_nodes.append(target_node)
        
        # Находим используемые узлы (исключая неиспользуемые)
        used_nodes = [n for n in node_tree.nodes if n not in all_nodes and n.type != 'FRAME']
        
        # Используем улучшенную функцию размещения с увеличенным отступом
        frame = place_group_left_of_used(node_tree, all_nodes, used_nodes, margin=400)
        
        if frame:
            frame.name = "UNUSED_FRAME"
            frame.label = "UNUSED"

    def _process_node_tree(self, node_tree: NodeTree, attr_text: str, attr_type: str = 'GEOMETRY', attr_channel: str = 'Color') -> bool:
        """Обработать дерево узлов для группировки.
        
        Args:
            node_tree: Дерево узлов для обработки
            attr_text: Текст атрибута
            attr_type: Тип атрибута
            attr_channel: Канал данных атрибута
            
        Returns:
            bool: True если обработка прошла успешно
        """
        # Удаляем существующий фрейм UNUSED_FRAME
        self._remove_existing_unused_frame(node_tree)
        
        # Удаляем старые атрибуты
        self._remove_old_attributes(node_tree)
        
        # Находим неиспользуемые узлы
        unused_dict = find_unused_nodes_recursive(node_tree)
        if not unused_dict:
            return False
        
        # Создаем пары (attribute_node, target_node)
        pairs: List[Tuple[Optional[Node], Node]] = []
        for node in unused_dict.keys():
            attr_node = self._add_attribute_node(node_tree, node, attr_text, attr_type, attr_channel)
            pairs.append((attr_node, node))
        
        # Создаем фрейм
        self._create_unused_frame(node_tree, pairs)
        
        return True


class NODE_OT_GroupUnusedNodesActive(BaseGroupUnusedNodes, Operator):
    """Группировать неиспользуемые узлы в активном дереве узлов."""
    
    bl_idname = "node.group_unused_nodes_active"
    bl_label = "Группировать неиспользуемые (активное дерево)"
    bl_description = "Собрать неиспользуемые узлы в сетку и обрамить в фрейм"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        """Выполнить группировку неиспользуемых узлов в активном дереве.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            tree = NodeTreeProcessor.get_active_node_tree(context)
            if not NodeTreeProcessor.validate_node_tree(tree, self):
                return {'CANCELLED'}
            
            attr_text = context.scene.unused_nodes_attr_text
            attr_type = context.scene.unused_nodes_attr_type
            attr_channel = context.scene.unused_nodes_attr_channel
            
            if self._process_node_tree(tree, attr_text, attr_type, attr_channel):
                self.report({'INFO'}, "Неиспользуемые узлы сгруппированы")
            else:
                self.report({'INFO'}, "Неиспользуемых узлов не найдено")
            
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при группировке неиспользуемых узлов: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при группировке: {str(e)}")
            return {'CANCELLED'}


class NODE_OT_GroupUnusedNodesAll(BaseGroupUnusedNodes, Operator):
    """Группировать неиспользуемые узлы во всех материалах проекта."""
    
    bl_idname = "node.group_unused_nodes_all"
    bl_label = "Группировать неиспользуемые (все материалы)"
    bl_description = "Собрать неиспользуемые узлы в сетку и обрамить в фрейм во всех материалах"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        """Выполнить группировку неиспользуемых узлов во всех материалах.
        
        Args:
            context: Контекст Blender
            
        Returns:
            Set[str]: Результат выполнения операции
        """
        try:
            attr_text = context.scene.unused_nodes_attr_text
            attr_type = context.scene.unused_nodes_attr_type
            attr_channel = context.scene.unused_nodes_attr_channel
            materials_processed = 0
            materials_with_unused = 0
            
            for material in bpy.data.materials:
                if material and material.use_nodes and material.node_tree:
                    if self._process_node_tree(material.node_tree, attr_text, attr_type, attr_channel):
                        materials_with_unused += 1
                    materials_processed += 1
            
            if materials_with_unused == 0:
                self.report({'INFO'}, "Неиспользуемых узлов не найдено")
            else:
                self.report({'INFO'}, f"Обработано {materials_processed} материалов, найдено неиспользуемых узлов в {materials_with_unused} материалах")
            
            return {'FINISHED'}
            
        except Exception as e:
            logger.error(f"Ошибка при группировке всех неиспользуемых узлов: {str(e)}")
            self.report({'ERROR'}, f"Ошибка при группировке: {str(e)}")
            return {'CANCELLED'}


# ============================================================================
# ЭКСПОРТ КЛАССОВ
# ============================================================================

__all__ = [
    'NODE_OT_DeleteUnusedNodes',
    'NODE_OT_DeleteAllUnusedNodes',
    'TEXT_OT_OpenUnusedNodesReport',
    'NODE_OT_FindUnusedNodesPopup',
    'NODE_OT_GroupUnusedNodesActive',
    'NODE_OT_GroupUnusedNodesAll',
    'TEXT_OT_OpenUnusedNodesReportWindow'
] 