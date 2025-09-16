# -*- coding: utf-8 -*-
"""Responsive grid system and adaptive layouts for Bascula-Cam"""

import tkinter as tk
from typing import Dict, List, Optional, Union, Tuple
from bascula.config.theme import get_current_colors

class ResponsiveGrid(tk.Frame):
    """Responsive grid container that adapts to screen size"""
    
    def __init__(self, parent, columns: int = 12, gutter: int = 16, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.columns = columns
        self.gutter = gutter
        self.items: List[Dict] = []
        
        # Configure grid weights
        for i in range(columns):
            self.grid_columnconfigure(i, weight=1)
        
        self.bind('<Configure>', self._on_resize)
    
    def add_item(self, widget: tk.Widget, col_span: Union[int, Dict[str, int]] = 1, 
                 row: Optional[int] = None, sticky: str = 'ew', **grid_kwargs):
        """Add item to responsive grid
        
        Args:
            widget: Widget to add
            col_span: Column span (int) or breakpoint dict {'xs': 12, 'sm': 6, 'md': 4, 'lg': 3}
            row: Specific row (auto if None)
            sticky: Grid sticky option
        """
        if isinstance(col_span, int):
            col_span = {'xs': col_span, 'sm': col_span, 'md': col_span, 'lg': col_span, 'xl': col_span}
        
        item = {
            'widget': widget,
            'col_span': col_span,
            'row': row,
            'sticky': sticky,
            'grid_kwargs': grid_kwargs
        }
        
        self.items.append(item)
        self._layout_items()
    
    def _get_breakpoint(self, width: int) -> str:
        """Determine current breakpoint based on width"""
        if width < 576:
            return 'xs'
        elif width < 768:
            return 'sm'
        elif width < 992:
            return 'md'
        elif width < 1200:
            return 'lg'
        else:
            return 'xl'
    
    def _layout_items(self):
        """Layout items based on current breakpoint"""
        self.update_idletasks()
        width = self.winfo_width()
        if width <= 1:
            self.after(100, self._layout_items)
            return
        
        breakpoint = self._get_breakpoint(width)
        
        current_row = 0
        current_col = 0
        
        for item in self.items:
            widget = item['widget']
            col_span = item['col_span'].get(breakpoint, item['col_span'].get('md', 1))
            
            # Check if we need to wrap to next row
            if current_col + col_span > self.columns:
                current_row += 1
                current_col = 0
            
            # Use specific row if provided
            if item['row'] is not None:
                current_row = item['row']
                current_col = 0
            
            # Grid the widget
            widget.grid(
                row=current_row,
                column=current_col,
                columnspan=col_span,
                sticky=item['sticky'],
                padx=(0, self.gutter if current_col + col_span < self.columns else 0),
                pady=(0, self.gutter),
                **item['grid_kwargs']
            )
            
            current_col += col_span
    
    def _on_resize(self, event):
        """Handle resize events"""
        if event.widget == self:
            self._layout_items()


class FlexContainer(tk.Frame):
    """Flexbox-like container for dynamic layouts"""
    
    def __init__(self, parent, direction: str = 'row', justify: str = 'start', 
                 align: str = 'stretch', wrap: bool = False, gap: int = 8, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.direction = direction  # 'row' or 'column'
        self.justify = justify      # 'start', 'center', 'end', 'space-between', 'space-around'
        self.align = align          # 'start', 'center', 'end', 'stretch'
        self.wrap = wrap
        self.gap = gap
        self.items: List[Dict] = []
        
        self.bind('<Configure>', self._layout_flex)
    
    def add_item(self, widget: tk.Widget, flex: int = 0, **pack_kwargs):
        """Add item to flex container
        
        Args:
            widget: Widget to add
            flex: Flex grow factor (0 = no grow, 1+ = proportional grow)
        """
        item = {
            'widget': widget,
            'flex': flex,
            'pack_kwargs': pack_kwargs
        }
        self.items.append(item)
        self._layout_flex()
    
    def _layout_flex(self, event=None):
        """Layout items using flexbox-like algorithm"""
        if not self.items:
            return
        
        # Clear current layout
        for item in self.items:
            item['widget'].pack_forget()
        
        # Calculate available space
        self.update_idletasks()
        if self.direction == 'row':
            available_space = self.winfo_width()
            total_gap = self.gap * (len(self.items) - 1)
        else:
            available_space = self.winfo_height()
            total_gap = self.gap * (len(self.items) - 1)
        
        # Calculate flex distribution
        total_flex = sum(item['flex'] for item in self.items)
        fixed_space = 0
        
        # First pass: calculate space for non-flex items
        for item in self.items:
            if item['flex'] == 0:
                widget = item['widget']
                if self.direction == 'row':
                    widget.pack(side='left', **item['pack_kwargs'])
                    widget.update_idletasks()
                    fixed_space += widget.winfo_reqwidth()
                else:
                    widget.pack(side='top', **item['pack_kwargs'])
                    widget.update_idletasks()
                    fixed_space += widget.winfo_reqheight()
                widget.pack_forget()
        
        flex_space = max(0, available_space - fixed_space - total_gap)
        
        # Second pass: layout all items
        for i, item in enumerate(self.items):
            widget = item['widget']
            
            pack_options = {
                'padx': (0, self.gap) if i < len(self.items) - 1 and self.direction == 'row' else 0,
                'pady': (0, self.gap) if i < len(self.items) - 1 and self.direction == 'column' else 0,
                **item['pack_kwargs']
            }
            
            if self.direction == 'row':
                side = 'left'
                if item['flex'] > 0 and total_flex > 0:
                    flex_width = int(flex_space * item['flex'] / total_flex)
                    pack_options['ipadx'] = max(0, flex_width - widget.winfo_reqwidth()) // 2
                
                if self.align == 'center':
                    pack_options['anchor'] = 'center'
                elif self.align == 'end':
                    pack_options['anchor'] = 's'
                elif self.align == 'stretch':
                    pack_options['fill'] = 'y'
            else:
                side = 'top'
                if item['flex'] > 0 and total_flex > 0:
                    flex_height = int(flex_space * item['flex'] / total_flex)
                    pack_options['ipady'] = max(0, flex_height - widget.winfo_reqheight()) // 2
                
                if self.align == 'center':
                    pack_options['anchor'] = 'center'
                elif self.align == 'end':
                    pack_options['anchor'] = 'e'
                elif self.align == 'stretch':
                    pack_options['fill'] = 'x'
            
            widget.pack(side=side, **pack_options)


class AdaptiveLayout(tk.Frame):
    """Layout that adapts based on screen size and orientation"""
    
    def __init__(self, parent, layouts: Dict[str, callable], **kwargs):
        super().__init__(parent, **kwargs)
        
        self.layouts = layouts  # {'mobile': func, 'tablet': func, 'desktop': func}
        self.current_layout = None
        self.current_layout_name = None
        
        self.bind('<Configure>', self._check_layout)
        self.after(100, self._check_layout)  # Initial layout check
    
    def _get_layout_type(self) -> str:
        """Determine layout type based on screen size"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        
        if width <= 600:
            return 'mobile'
        elif width <= 1024:
            return 'tablet'
        else:
            return 'desktop'
    
    def _check_layout(self, event=None):
        """Check if layout needs to change"""
        layout_type = self._get_layout_type()
        
        if layout_type != self.current_layout_name:
            self._apply_layout(layout_type)
    
    def _apply_layout(self, layout_type: str):
        """Apply the specified layout"""
        if layout_type not in self.layouts:
            return
        
        # Clear current layout
        for widget in self.winfo_children():
            widget.destroy()
        
        # Apply new layout
        self.current_layout_name = layout_type
        self.current_layout = self.layouts[layout_type](self)


class CardGrid(ResponsiveGrid):
    """Specialized responsive grid for card layouts"""
    
    def __init__(self, parent, **kwargs):
        colors = get_current_colors()
        super().__init__(parent, bg=colors['COL_BG'], **kwargs)
    
    def add_card(self, title: str, content_func: callable, 
                 col_span: Union[int, Dict[str, int]] = {'xs': 12, 'sm': 6, 'md': 4, 'lg': 3}):
        """Add a card to the grid"""
        from bascula.ui.modern_widgets import ModernCard
        
        card = ModernCard(self, title=title)
        content_func(card.content_frame)
        
        self.add_item(card, col_span=col_span, sticky='nsew')
        return card


class SidebarLayout(tk.Frame):
    """Layout with collapsible sidebar"""
    
    def __init__(self, parent, sidebar_width: int = 250, **kwargs):
        colors = get_current_colors()
        super().__init__(parent, bg=colors['COL_BG'], **kwargs)
        
        self.sidebar_width = sidebar_width
        self.sidebar_collapsed = False
        
        # Create sidebar
        self.sidebar = tk.Frame(self, bg=colors['COL_CARD'], width=sidebar_width)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        
        # Sidebar toggle button
        self.toggle_btn = tk.Button(
            self.sidebar,
            text='◀',
            command=self.toggle_sidebar,
            bg=colors['COL_ACCENT'],
            fg='white',
            relief='flat',
            bd=0
        )
        self.toggle_btn.pack(anchor='ne', padx=5, pady=5)
        
        # Main content area
        self.content = tk.Frame(self, bg=colors['COL_BG'])
        self.content.pack(side='right', fill='both', expand=True)
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility"""
        if self.sidebar_collapsed:
            self.sidebar.pack(side='left', fill='y', before=self.content)
            self.toggle_btn.configure(text='◀')
            self.sidebar_collapsed = False
        else:
            self.sidebar.pack_forget()
            self.toggle_btn.configure(text='▶')
            self.sidebar_collapsed = True
    
    def add_sidebar_item(self, widget: tk.Widget, **pack_kwargs):
        """Add item to sidebar"""
        widget.pack(in_=self.sidebar, **pack_kwargs)
    
    def add_content(self, widget: tk.Widget, **pack_kwargs):
        """Add content to main area"""
        widget.pack(in_=self.content, **pack_kwargs)


# Utility functions
def create_responsive_button_row(parent, buttons: List[Dict], **kwargs):
    """Create a responsive row of buttons"""
    container = FlexContainer(parent, direction='row', justify='space-between', **kwargs)
    
    for btn_config in buttons:
        from bascula.ui.modern_widgets import ModernButton
        btn = ModernButton(container, **btn_config)
        container.add_item(btn, flex=1)
    
    return container


def create_form_layout(parent, fields: List[Dict], **kwargs):
    """Create a responsive form layout"""
    from bascula.ui.modern_widgets import ModernInput
    
    grid = ResponsiveGrid(parent, **kwargs)
    
    for i, field in enumerate(fields):
        col_span = field.get('col_span', {'xs': 12, 'sm': 6})
        input_field = ModernInput(grid, **field)
        grid.add_item(input_field, col_span=col_span)
    
    return grid
