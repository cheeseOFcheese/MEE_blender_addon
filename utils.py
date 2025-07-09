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

Вспомогательные функции для аддона неиспользуемых узлов.
"""

import bpy
import logging
import os
from typing import List, Set, Tuple, Optional, Dict
from bpy.types import Node, NodeTree, Material, NodeLink
from datetime import datetime
import math


def setup_logging() -> None:
    """Настройка логирования для аддона."""
    log_file = os.path.join(bpy.app.tempdir, 'unused_nodes.log')
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Логирование аддона неиспользуемых узлов инициализировано. Файл лога: {log_file}")


def get_output_nodes(node_tree: NodeTree) -> List[Node]:
    """Получить все выходные узлы из дерева узлов.
    
    Args:
        node_tree: Дерево узлов для анализа
        
    Returns:
        List[Node]: Список выходных узлов
    """
    output_types = {
        'OUTPUT_MATERIAL', 'OUTPUT_WORLD', 'OUTPUT_LIGHT',
        'CompositorNodeComposite', 'CompositorNodeOutputFile',
        'CompositorNodeViewer', 'NodeGroupOutput'
    }
    
    output_nodes: List[Node] = []
    for node in node_tree.nodes:
        if node.type in output_types:
            output_nodes.append(node)
    
    return output_nodes





def traverse_from_outputs(tree: NodeTree) -> Set[Node]:
    """Обойти дерево от выходных узлов и найти все используемые узлы.
    
    Args:
        tree: Дерево узлов для анализа
        
    Returns:
        Set[Node]: Множество используемых узлов
    """
    used: Set[Node] = set()
    
    def visit(node: Node) -> None:
        if node in used:
            return
        used.add(node)
        for inp in node.inputs:
            for link in inp.links:
                visit(link.from_node)
        for out in node.outputs:
            for link in out.links:
                visit(link.to_node)
    
    for out_node in get_output_nodes(tree):
        visit(out_node)
    
    return used





def find_unused_nodes(node_tree: NodeTree, parent_tree_name: str = "", show_attributes: bool = True) -> Dict[Node, Dict]:
    """Найти неиспользуемые узлы в дереве узлов с расширенной информацией.
    
    Args:
        node_tree: Дерево узлов для анализа
        parent_tree_name: Имя родительского дерева для вложенных групп
        show_attributes: Показывать ли атрибуты в отчете
        
    Returns:
        Dict[Node, Dict]: Словарь {node: {"type": str, "materials": List[str], "parent_tree": str}}
    """
    if not node_tree:
        return {}
    
    # Получаем все выходные узлы
    output_nodes = get_output_nodes(node_tree)
    if not output_nodes:
        return {}
    
    # Находим все используемые узлы, проходя от выходных узлов
    used_nodes = traverse_from_outputs(node_tree)
    
    # Находим неиспользуемые узлы (исключая сами выходные узлы)
    all_nodes = set(node_tree.nodes)
    unused_nodes = all_nodes - used_nodes
    
    # Фильтруем атрибуты, если show_attributes=False
    if not show_attributes:
        unused_nodes = {node for node in unused_nodes 
                       if not (node.type == 'ATTRIBUTE' or 
                              node.bl_idname in {'ShaderNodeAttribute', 'GeometryNodeInputNamedAttribute'})}
    
    # Создаем словарь с информацией о неиспользуемых узлах
    unused_dict = {}
    tree_name = parent_tree_name if parent_tree_name else node_tree.name
    
    for node in unused_nodes:
        unused_dict[node] = {
            "type": node.type,
            "materials": [],  # для групп будет заполнено позже
            "connected_to_output": [],  # для групп - материалы где группа подключена к выходу
            "parent_tree": tree_name
        }
    
    return unused_dict


def collect_group_usage(unused_dict: Dict[Node, Dict], materials: List[Material]) -> None:
    """Собрать информацию о том, в каких материалах используются группы.
    
    Args:
        unused_dict: Словарь неиспользуемых узлов
        materials: Список материалов для анализа
    """
    for material in materials:
        if not material.use_nodes or not material.node_tree:
            continue
            
        for node in material.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree:
                # Ищем эту группу в словаре неиспользуемых узлов
                for unused_node, info in unused_dict.items():
                    if (unused_node.type == 'GROUP' and 
                        unused_node.node_tree == node.node_tree and
                        material.name not in info["materials"]):
                        info["materials"].append(material.name)
                        
                        # Проверяем, подключена ли группа к выходу в этом материале
                        if "connected_to_output" not in info:
                            info["connected_to_output"] = []
                        if material.name not in info["connected_to_output"]:
                            if is_group_connected_to_output(node, material.node_tree):
                                info["connected_to_output"].append(material.name)


def find_unused_nodes_recursive(node_tree: NodeTree, parent_tree_name: str = "", show_attributes: bool = True) -> Dict[Node, Dict]:
    """Рекурсивно найти неиспользуемые узлы, включая вложенные группы.
    
    Args:
        node_tree: Дерево узлов для анализа
        parent_tree_name: Имя родительского дерева для вложенности
        show_attributes: Показывать ли атрибуты в отчете
        
    Returns:
        Dict[Node, Dict]: Объединенный словарь всех неиспользуемых узлов
    """
    if not node_tree:
        return {}
    
    # Получаем неиспользуемые узлы в текущем дереве
    unused_dict = find_unused_nodes(node_tree, parent_tree_name, show_attributes)
    
    # Рекурсивно обрабатываем групповые узлы
    for node in list(unused_dict.keys()):
        if node.type == 'GROUP' and node.node_tree:
            # Создаем имя для вложенного дерева
            nested_tree_name = f"{parent_tree_name}.{node.name}" if parent_tree_name else node.name
            
            # Рекурсивно находим неиспользуемые узлы в группе
            nested_unused = find_unused_nodes_recursive(node.node_tree, nested_tree_name, show_attributes)
            
            # Объединяем результаты
            unused_dict.update(nested_unused)
    
    return unused_dict


def remove_tmp_attribute_nodes(node_tree: NodeTree) -> None:
    """Удалить Attribute-ноды, созданные прошлым запуском аддона.
    
    Args:
        node_tree: Дерево узлов для очистки
    """
    nodes_to_remove: List[Node] = []
    for node in list(node_tree.nodes):  # list() для безопасного изменения коллекции
        # Проверяем разные типы Attribute-нод и метку
        if ((node.type == 'ATTRIBUTE' or 
             node.bl_idname in {'ShaderNodeAttribute', 'GeometryNodeInputNamedAttribute'}) and 
            getattr(node, 'label', '') == '_tmp_attr'):
            nodes_to_remove.append(node)
    
    # Удаляем найденные ноды
    for node in nodes_to_remove:
        node_tree.nodes.remove(node)


def layout_nodes_grid(nodes: List[Node], cols: int = 6, gap_x: float = 120.0, gap_y: float = 80.0) -> None:
    """Умная сетка, сохраняющая равномерные ширины столбцов/высоты строк.
    
    Args:
        nodes: Список узлов для размещения
        cols: Количество столбцов
        gap_x: Горизонтальный отступ между узлами
        gap_y: Вертикальный отступ между узлами
    """
    if not nodes:
        return
    
    # Разделяем атрибуты и обычные ноды для лучшего размещения
    attr_nodes = [n for n in nodes if getattr(n, 'label', '') == '_tmp_attr']
    regular_nodes = [n for n in nodes if getattr(n, 'label', '') != '_tmp_attr']
    
    # Создаем словарь для связи атрибутов с их родительскими нодами
    attr_to_parent: Dict[Node, Node] = {}
    for attr in attr_nodes:
        # Ищем родительскую ноду по имени (убираем префикс "Attr_")
        parent_name = attr.name.replace("Attr_", "")
        for parent in regular_nodes:
            if parent.name == parent_name:
                attr_to_parent[attr] = parent
                break
    
    # Размещаем обычные ноды в сетке
    if regular_nodes:
        regular_nodes = sorted(regular_nodes, key=lambda n: (-n.location.y, n.location.x))
        col_w = [0.0] * cols
        row_h: List[float] = []
        grid: List[List[Node]] = []
        
        for i, node in enumerate(regular_nodes):
            c = i % cols
            r = i // cols
            if len(grid) <= r:
                grid.append([])
                row_h.append(0.0)
            grid[r].append(node)
            col_w[c] = max(col_w[c], getattr(node, 'width', 100.0))
            row_h[r] = max(row_h[r], getattr(node, 'dimensions', (100.0, 100.0))[1])
        
        origin_x = min(n.location.x for n in regular_nodes)
        origin_y = max(n.location.y for n in regular_nodes)
        
        for r, row in enumerate(grid):
            y = origin_y - sum(row_h[:r]) - r * gap_y
            for c, n in enumerate(row):
                x = origin_x + sum(col_w[:c]) + c * gap_x
                n.location = (x, y)
        
        # Размещаем атрибуты слева от их родительских нод
        for attr, parent in attr_to_parent.items():
            attr.location.x = parent.location.x - 150.0  # Отступ слева
            attr.location.y = parent.location.y        # Та же высота





def place_group_left_of_used(tree: NodeTree, group_nodes: List[Node], used_nodes: List[Node], margin: float = 400.0) -> Optional[Node]:
    """Разместить группу узлов слева от используемых узлов.
    
    Args:
        tree: Дерево узлов
        group_nodes: Список узлов для группировки
        used_nodes: Список используемых узлов
        margin: Отступ от используемых узлов
        
    Returns:
        Optional[Node]: Созданный фрейм или None
    """
    if not group_nodes:
        return None
    
    # Сетка внутри фрейма
    layout_nodes_grid(group_nodes)
    
    # Сдвиг слева от используемых (увеличиваем отступ в 2 раза)
    used_min_x = min((n.location.x for n in used_nodes), default=0.0)
    max_group_x = max(n.location.x for n in group_nodes)
    dx = (used_min_x - margin) - max_group_x
    
    for n in group_nodes:
        n.location.x += dx
    
    # Создание фрейма
    xs = [n.location.x for n in group_nodes]
    ys = [n.location.y for n in group_nodes]
    
    frame = tree.nodes.new("NodeFrame")
    frame.label = "The Material Editor Exterminatus"
    frame.location = (min(xs) - 40.0, max(ys) + 40.0)
    frame.width = 0
    
    for n in group_nodes:
        n.parent = frame
    
    return frame








def is_group_connected_to_output(group_node: Node, node_tree: NodeTree) -> bool:
    """Проверить, подключена ли группа к выходному узлу.
    
    Args:
        group_node: Групповой узел для проверки
        node_tree: Дерево узлов, содержащее группу
        
    Returns:
        bool: True если группа подключена к выходу, False иначе
    """
    if not group_node or not node_tree:
        return False
    
    # Проверяем, есть ли у группы подключенные выходы
    if not group_node.outputs:
        return False
    
    # Проверяем каждый выход группы
    for output_socket in group_node.outputs:
        if output_socket.is_linked:
            # Если есть хотя бы одно подключение, группа подключена
            return True
    
    # Если ни один выход не подключен, группа не подключена
    return False





 