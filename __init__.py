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

Аддон для поиска и управления неиспользуемыми узлами в Blender.

Этот аддон помогает находить неиспользуемые узлы в материалах,
создавать подробные отчеты и управлять ими различными способами.
"""

import bpy
import logging
from typing import List

# Импорт модулей аддона
from . import operators
from . import ui
from . import utils

# Настройка логирования
logger = logging.getLogger(__name__)


def register() -> None:
    """Зарегистрировать аддон."""
    try:
        # Настройка логирования
        utils.setup_logging()
        
        # Регистрация операторов
        operators_classes = [
            operators.NODE_OT_DeleteUnusedNodes,
            operators.NODE_OT_DeleteAllUnusedNodes,
            operators.NODE_OT_SimpleReportPopup,
            operators.NODE_OT_FindUnusedNodesPopup,
            operators.TEXT_OT_OpenUnusedNodesReport,
            operators.TEXT_OT_OpenUnusedNodesReportWindow,
            operators.NODE_OT_GroupUnusedNodesActive,
            operators.NODE_OT_GroupUnusedNodesAll,
        ]
        
        for cls in operators_classes:
            bpy.utils.register_class(cls)
        
        # Регистрация UI
        ui.register()
        
        logger.info("Аддон The Material Editor Exterminatus успешно зарегистрирован")
        
    except Exception as e:
        logger.error(f"Ошибка при регистрации аддона: {str(e)}")
        raise


def unregister() -> None:
    """Отменить регистрацию аддона."""
    try:
        # Отмена регистрации UI
        ui.unregister()
        
        # Отмена регистрации операторов
        operators_classes = [
            operators.NODE_OT_GroupUnusedNodesAll,
            operators.NODE_OT_GroupUnusedNodesActive,
            operators.TEXT_OT_OpenUnusedNodesReportWindow,
            operators.TEXT_OT_OpenUnusedNodesReport,
            operators.NODE_OT_FindUnusedNodesPopup,
            operators.NODE_OT_SimpleReportPopup,
            operators.NODE_OT_DeleteAllUnusedNodes,
            operators.NODE_OT_DeleteUnusedNodes,
        ]
        
        for cls in operators_classes:
            bpy.utils.unregister_class(cls)
        
        logger.info("Аддон The Material Editor Exterminatus успешно отменен")
        
    except Exception as e:
        logger.error(f"Ошибка при отмене регистрации аддона: {str(e)}")
        raise


if __name__ == "__main__":
    register() 