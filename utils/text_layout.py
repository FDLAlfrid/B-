# 文本布局和测量模块
# 模拟pretext库的功能，用于PyQt5项目

from typing import List, Dict, Any, Tuple, Optional
from PyQt5.QtGui import QFontMetrics, QFont, QPainter
from PyQt5.QtCore import QRect


class TextLayout:
    """文本布局和测量工具
    
    模拟pretext库的功能，提供高效的文本测量和布局能力
    避免使用可能触发布局重排的DOM测量方法
    """
    
    def __init__(self):
        """初始化文本布局工具"""
        self.font_metrics_cache = {}
    
    def get_font_metrics(self, font: QFont) -> QFontMetrics:
        """获取字体度量信息，使用缓存提高性能
        
        Args:
            font: QFont对象
            
        Returns:
            QFontMetrics: 字体度量信息
        """
        font_key = (font.family(), font.pointSize(), font.weight(), font.italic())
        if font_key not in self.font_metrics_cache:
            self.font_metrics_cache[font_key] = QFontMetrics(font)
        return self.font_metrics_cache[font_key]
    
    def measure_text(self, text: str, font: QFont) -> Dict[str, int]:
        """测量文本尺寸
        
        Args:
            text: 要测量的文本
            font: 字体对象
            
        Returns:
            Dict: 包含宽度和高度的字典
        """
        metrics = self.get_font_metrics(font)
        rect = metrics.boundingRect(text)
        return {
            'width': rect.width(),
            'height': rect.height()
        }
    
    def layout_text(self, text: str, font: QFont, max_width: int) -> Dict[str, Any]:
        """布局文本，计算换行和高度
        
        Args:
            text: 要布局的文本
            font: 字体对象
            max_width: 最大宽度
            
        Returns:
            Dict: 包含高度、行数和每行文本的字典
        """
        metrics = self.get_font_metrics(font)
        lines = []
        current_line = ""
        current_width = 0
        
        words = text.split()
        
        for word in words:
            word_width = metrics.width(word)
            
            if current_line:
                space_width = metrics.width(' ')
                if current_width + space_width + word_width <= max_width:
                    current_line += ' ' + word
                    current_width += space_width + word_width
                else:
                    lines.append(current_line)
                    current_line = word
                    current_width = word_width
            else:
                current_line = word
                current_width = word_width
        
        if current_line:
            lines.append(current_line)
        
        line_height = metrics.height()
        total_height = line_height * len(lines)
        
        return {
            'height': total_height,
            'line_count': len(lines),
            'lines': lines,
            'line_height': line_height
        }
    
    def measure_paragraph(self, text: str, font: QFont, max_width: int) -> Dict[str, Any]:
        """测量段落高度（模拟pretext的核心功能）
        
        Args:
            text: 段落文本
            font: 字体对象
            max_width: 最大宽度
            
        Returns:
            Dict: 包含高度和行数的字典
        """
        result = self.layout_text(text, font, max_width)
        return {
            'height': result['height'],
            'line_count': result['line_count']
        }
    
    def layout_with_lines(self, text: str, font: QFont, max_width: int) -> Dict[str, Any]:
        """布局文本并返回详细的行信息
        
        Args:
            text: 要布局的文本
            font: 字体对象
            max_width: 最大宽度
            
        Returns:
            Dict: 包含高度、行数和每行详细信息的字典
        """
        result = self.layout_text(text, font, max_width)
        metrics = self.get_font_metrics(font)
        
        line_details = []
        for line in result['lines']:
            line_width = metrics.width(line)
            line_details.append({
                'text': line,
                'width': line_width
            })
        
        return {
            'height': result['height'],
            'line_count': result['line_count'],
            'lines': line_details
        }
    
    def calculate_optimal_width(self, text: str, font: QFont) -> int:
        """计算文本的最佳宽度（最窄容器宽度）
        
        Args:
            text: 文本内容
            font: 字体对象
            
        Returns:
            int: 最佳宽度
        """
        metrics = self.get_font_metrics(font)
        words = text.split()
        max_word_width = 0
        
        for word in words:
            word_width = metrics.width(word)
            if word_width > max_word_width:
                max_word_width = word_width
        
        return max_word_width
    
    def draw_text_with_layout(self, painter: QPainter, text: str, font: QFont, 
                            rect: QRect, align: int = 0) -> None:
        """使用优化的布局绘制文本
        
        Args:
            painter: QPainter对象
            text: 要绘制的文本
            font: 字体对象
            rect: 绘制区域
            align: 对齐方式
        """
        layout_result = self.layout_text(text, font, rect.width())
        metrics = self.get_font_metrics(font)
        
        y = rect.top() + metrics.ascent()
        for line in layout_result['lines']:
            painter.drawText(rect.left(), y, line)
            y += layout_result['line_height']


# 创建全局文本布局实例
text_layout = TextLayout()