# -*- coding: utf-8 -*-
"""
Modern Navigation Components for Bascula-Cam UI
Provides breadcrumbs, improved tabs, and navigation utilities
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Callable, Optional, Any
from bascula.config.theme import get_current_colors
from bascula.ui.widgets import get_scaled_size, TOUCH_MIN_SIZE, FS_TEXT, FS_BTN_SMALL

# Get theme colors
pal = get_current_colors()
COL_BG = pal['COL_BG']
COL_CARD = pal['COL_CARD']
COL_TEXT = pal['COL_TEXT']
COL_ACCENT = pal['COL_ACCENT']
COL_MUTED = pal['COL_MUTED']
COL_CARD_HOVER = pal.get('COL_CARD_HOVER', COL_CARD)
COL_SHADOW = pal.get('COL_SHADOW', '#00000020')


class Breadcrumb(tk.Frame):
    """Modern breadcrumb navigation component"""
    
    def __init__(self, parent, navigation_callback: Callable[[str], None] = None, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.navigation_callback = navigation_callback
        self.breadcrumb_items = []
        self.item_widgets = []
        
        # Main container with padding
        self.container = tk.Frame(self, bg=COL_CARD)
        self.container.pack(fill='x', padx=get_scaled_size(16), pady=get_scaled_size(8))
        
    def set_path(self, path_items: List[Dict[str, Any]]):
        """
        Set breadcrumb path
        path_items: List of dicts with 'label', 'screen_name', and optional 'icon'
        Example: [{'label': 'Home', 'screen_name': 'home', 'icon': '🏠'}, 
                  {'label': 'Settings', 'screen_name': 'settings'}]
        """
        # Clear existing widgets
        for widget in self.item_widgets:
            widget.destroy()
        self.item_widgets.clear()
        
        self.breadcrumb_items = path_items
        
        for i, item in enumerate(path_items):
            is_last = (i == len(path_items) - 1)
            
            # Create breadcrumb item
            item_frame = tk.Frame(self.container, bg=COL_CARD)
            item_frame.pack(side='left', padx=get_scaled_size(2))
            
            # Icon if provided
            if item.get('icon'):
                icon_label = tk.Label(item_frame, text=item['icon'], 
                                    bg=COL_CARD, fg=COL_TEXT,
                                    font=("DejaVu Sans", FS_TEXT))
                icon_label.pack(side='left', padx=(0, get_scaled_size(4)))
            
            # Label - clickable if not last item
            if is_last:
                # Current page - not clickable, different style
                label = tk.Label(item_frame, text=item['label'],
                               bg=COL_CARD, fg=COL_ACCENT,
                               font=("DejaVu Sans", FS_TEXT, "bold"))
                label.pack(side='left')
            else:
                # Previous pages - clickable
                label = tk.Label(item_frame, text=item['label'],
                               bg=COL_CARD, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TEXT),
                               cursor="hand2")
                label.pack(side='left')
                
                # Make clickable
                screen_name = item['screen_name']
                label.bind("<Button-1>", lambda e, s=screen_name: self._navigate_to(s))
                label.bind("<Enter>", lambda e, l=label: l.config(fg=COL_ACCENT))
                label.bind("<Leave>", lambda e, l=label: l.config(fg=COL_TEXT))
            
            self.item_widgets.extend([item_frame, label])
            
            # Add separator if not last item
            if not is_last:
                separator = tk.Label(self.container, text="›", 
                                   bg=COL_CARD, fg=COL_MUTED,
                                   font=("DejaVu Sans", FS_TEXT))
                separator.pack(side='left', padx=get_scaled_size(8))
                self.item_widgets.append(separator)
    
    def _navigate_to(self, screen_name: str):
        """Handle navigation to a breadcrumb item"""
        if self.navigation_callback:
            self.navigation_callback(screen_name)


class ModernTabBar(tk.Frame):
    """Modern tab bar with improved styling and touch-friendly design"""
    
    def __init__(self, parent, on_tab_change: Callable[[str], None] = None, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.on_tab_change = on_tab_change
        self.tabs = {}
        self.active_tab = None
        self.tab_buttons = {}
        
        # Tab container with shadow effect
        self.tab_container = tk.Frame(self, bg=COL_CARD, relief='flat', bd=0)
        self.tab_container.pack(fill='x', padx=get_scaled_size(8), pady=get_scaled_size(4))
        
        # Active tab indicator
        self.indicator = tk.Frame(self.tab_container, bg=COL_ACCENT, height=get_scaled_size(3))
        self.indicator_position = 0
        
    def add_tab(self, tab_id: str, label: str, icon: str = None, enabled: bool = True):
        """Add a new tab"""
        tab_frame = tk.Frame(self.tab_container, bg=COL_CARD)
        tab_frame.pack(side='left', padx=get_scaled_size(2))
        
        # Create tab button with modern styling
        tab_button = tk.Frame(tab_frame, bg=COL_CARD, cursor="hand2" if enabled else "")
        tab_button.pack(fill='both', expand=True, 
                       padx=get_scaled_size(8), pady=get_scaled_size(8))
        
        # Ensure minimum touch target size
        min_width = max(TOUCH_MIN_SIZE, get_scaled_size(80))
        min_height = max(TOUCH_MIN_SIZE, get_scaled_size(40))
        
        # Icon and label container
        content_frame = tk.Frame(tab_button, bg=COL_CARD)
        content_frame.pack(expand=True)
        
        if icon:
            icon_label = tk.Label(content_frame, text=icon, 
                                bg=COL_CARD, fg=COL_MUTED if not enabled else COL_TEXT,
                                font=("DejaVu Sans", FS_TEXT))
            icon_label.pack(side='top', pady=(0, get_scaled_size(2)))
        
        text_label = tk.Label(content_frame, text=label,
                            bg=COL_CARD, fg=COL_MUTED if not enabled else COL_TEXT,
                            font=("DejaVu Sans", FS_BTN_SMALL, "normal"))
        text_label.pack(side='top')
        
        # Store tab info
        self.tabs[tab_id] = {
            'frame': tab_frame,
            'button': tab_button,
            'content_frame': content_frame,
            'icon_label': icon_label if icon else None,
            'text_label': text_label,
            'enabled': enabled,
            'label': label,
            'icon': icon
        }
        
        if enabled:
            # Bind click events
            for widget in [tab_button, content_frame, text_label] + ([icon_label] if icon else []):
                widget.bind("<Button-1>", lambda e, tid=tab_id: self._on_tab_click(tid))
                widget.bind("<Enter>", lambda e, tid=tab_id: self._on_tab_hover(tid, True))
                widget.bind("<Leave>", lambda e, tid=tab_id: self._on_tab_hover(tid, False))
        
        # Set first tab as active if none set
        if self.active_tab is None and enabled:
            self.set_active_tab(tab_id)
    
    def _on_tab_click(self, tab_id: str):
        """Handle tab click"""
        if self.tabs[tab_id]['enabled'] and tab_id != self.active_tab:
            self.set_active_tab(tab_id)
            if self.on_tab_change:
                self.on_tab_change(tab_id)
    
    def _on_tab_hover(self, tab_id: str, is_hover: bool):
        """Handle tab hover effects"""
        if not self.tabs[tab_id]['enabled'] or tab_id == self.active_tab:
            return
        
        tab_info = self.tabs[tab_id]
        hover_color = COL_CARD_HOVER if is_hover else COL_CARD
        text_color = COL_ACCENT if is_hover else COL_TEXT
        
        # Update colors
        for widget in [tab_info['button'], tab_info['content_frame']]:
            widget.config(bg=hover_color)
        
        tab_info['text_label'].config(bg=hover_color, fg=text_color)
        if tab_info['icon_label']:
            tab_info['icon_label'].config(bg=hover_color, fg=text_color)
    
    def set_active_tab(self, tab_id: str):
        """Set the active tab"""
        if tab_id not in self.tabs or not self.tabs[tab_id]['enabled']:
            return
        
        # Deactivate previous tab
        if self.active_tab and self.active_tab in self.tabs:
            prev_tab = self.tabs[self.active_tab]
            for widget in [prev_tab['button'], prev_tab['content_frame']]:
                widget.config(bg=COL_CARD)
            prev_tab['text_label'].config(bg=COL_CARD, fg=COL_TEXT, 
                                        font=("DejaVu Sans", FS_BTN_SMALL, "normal"))
            if prev_tab['icon_label']:
                prev_tab['icon_label'].config(bg=COL_CARD, fg=COL_TEXT)
        
        # Activate new tab
        self.active_tab = tab_id
        active_tab = self.tabs[tab_id]
        
        for widget in [active_tab['button'], active_tab['content_frame']]:
            widget.config(bg=COL_CARD)
        
        active_tab['text_label'].config(bg=COL_CARD, fg=COL_ACCENT,
                                      font=("DejaVu Sans", FS_BTN_SMALL, "bold"))
        if active_tab['icon_label']:
            active_tab['icon_label'].config(bg=COL_CARD, fg=COL_ACCENT)
        
        # Update indicator position (simplified - could be animated)
        self._update_indicator()
    
    def _update_indicator(self):
        """Update the position of the active tab indicator"""
        if not self.active_tab:
            return
        
        # Place indicator under active tab
        active_tab = self.tabs[self.active_tab]
        self.indicator.place(in_=active_tab['frame'], x=0, rely=1.0, 
                           relwidth=1.0, height=get_scaled_size(3))
    
    def enable_tab(self, tab_id: str, enabled: bool = True):
        """Enable or disable a tab"""
        if tab_id not in self.tabs:
            return
        
        tab_info = self.tabs[tab_id]
        tab_info['enabled'] = enabled
        
        # Update visual state
        color = COL_TEXT if enabled else COL_MUTED
        cursor = "hand2" if enabled else ""
        
        tab_info['button'].config(cursor=cursor)
        tab_info['text_label'].config(fg=color)
        if tab_info['icon_label']:
            tab_info['icon_label'].config(fg=color)


class NavigationDrawer(tk.Frame):
    """Modern slide-out navigation drawer"""
    
    def __init__(self, parent, width: int = None, **kwargs):
        self.drawer_width = width or get_scaled_size(280)
        super().__init__(parent, bg=COL_CARD, width=self.drawer_width, **kwargs)
        
        self.is_open = False
        self.animation_running = False
        self.navigation_callback = None
        
        # Header
        self.header = tk.Frame(self, bg=COL_ACCENT, height=get_scaled_size(60))
        self.header.pack(fill='x')
        self.header.pack_propagate(False)
        
        self.header_label = tk.Label(self.header, text="Navegación", 
                                   bg=COL_ACCENT, fg='white',
                                   font=("DejaVu Sans", FS_TEXT, "bold"))
        self.header_label.pack(expand=True)
        
        # Navigation items container
        self.nav_container = tk.Frame(self, bg=COL_CARD)
        self.nav_container.pack(fill='both', expand=True, padx=get_scaled_size(8))
        
        # Initially hidden
        self.place_forget()
    
    def add_nav_item(self, label: str, screen_name: str, icon: str = None, 
                    callback: Callable[[str], None] = None):
        """Add a navigation item"""
        item_frame = tk.Frame(self.nav_container, bg=COL_CARD, cursor="hand2")
        item_frame.pack(fill='x', pady=get_scaled_size(2))
        
        # Ensure touch-friendly height
        item_frame.config(height=max(TOUCH_MIN_SIZE, get_scaled_size(48)))
        
        content_frame = tk.Frame(item_frame, bg=COL_CARD)
        content_frame.pack(fill='both', expand=True, padx=get_scaled_size(16), 
                          pady=get_scaled_size(12))
        
        if icon:
            icon_label = tk.Label(content_frame, text=icon, bg=COL_CARD, fg=COL_TEXT,
                                font=("DejaVu Sans", FS_TEXT))
            icon_label.pack(side='left', padx=(0, get_scaled_size(12)))
        
        text_label = tk.Label(content_frame, text=label, bg=COL_CARD, fg=COL_TEXT,
                            font=("DejaVu Sans", FS_TEXT), anchor='w')
        text_label.pack(side='left', fill='x', expand=True)
        
        # Bind events
        nav_callback = callback or self.navigation_callback
        for widget in [item_frame, content_frame, text_label] + ([icon_label] if icon else []):
            widget.bind("<Button-1>", lambda e, s=screen_name: self._navigate_to(s, nav_callback))
            widget.bind("<Enter>", lambda e, f=item_frame: f.config(bg=COL_CARD_HOVER))
            widget.bind("<Leave>", lambda e, f=item_frame: f.config(bg=COL_CARD))
    
    def _navigate_to(self, screen_name: str, callback: Callable[[str], None] = None):
        """Handle navigation"""
        if callback:
            callback(screen_name)
        self.close()
    
    def open(self):
        """Open the drawer with animation"""
        if self.is_open or self.animation_running:
            return
        
        self.animation_running = True
        self.is_open = True
        
        # Place drawer off-screen initially
        self.place(x=-self.drawer_width, y=0, relheight=1.0, width=self.drawer_width)
        
        # Animate slide in
        self._animate_slide(target_x=0, callback=lambda: setattr(self, 'animation_running', False))
    
    def close(self):
        """Close the drawer with animation"""
        if not self.is_open or self.animation_running:
            return
        
        self.animation_running = True
        self.is_open = False
        
        # Animate slide out
        self._animate_slide(target_x=-self.drawer_width, 
                          callback=lambda: (self.place_forget(), 
                                          setattr(self, 'animation_running', False)))
    
    def _animate_slide(self, target_x: int, callback: Callable = None, step: int = 0):
        """Simple slide animation"""
        current_x = self.winfo_x()
        steps = 10
        
        if step >= steps:
            self.place(x=target_x, y=0, relheight=1.0, width=self.drawer_width)
            if callback:
                callback()
            return
        
        # Calculate intermediate position
        progress = step / steps
        new_x = current_x + (target_x - current_x) * 0.3
        
        self.place(x=int(new_x), y=0, relheight=1.0, width=self.drawer_width)
        self.after(30, lambda: self._animate_slide(target_x, callback, step + 1))
    
    def toggle(self):
        """Toggle drawer open/closed"""
        if self.is_open:
            self.close()
        else:
            self.open()


class NavigationManager:
    """Manages navigation state and history for the application"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.history = []
        self.current_screen = None
        
        # Screen hierarchy for breadcrumbs
        self.screen_hierarchy = {
            'home': {'label': 'Inicio', 'icon': '🏠', 'parent': None},
            'scale': {'label': 'Báscula', 'icon': '⚖️', 'parent': 'home'},
            'scanner': {'label': 'Escáner', 'icon': '📷', 'parent': 'home'},
            'settingsmenu': {'label': 'Ajustes', 'icon': '⚙️', 'parent': 'home'},
            'settings': {'label': 'Configuración', 'icon': '🔧', 'parent': 'settingsmenu'},
            'wifi': {'label': 'Wi-Fi', 'icon': '📶', 'parent': 'settingsmenu'},
            'nightscout': {'label': 'Nightscout', 'icon': '🩸', 'parent': 'settingsmenu'},
            'apikey': {'label': 'API Key', 'icon': '🔑', 'parent': 'settingsmenu'},
            'calib': {'label': 'Calibración', 'icon': '⚖️', 'parent': 'settingsmenu'},
        }
    
    def navigate_to(self, screen_name: str, add_to_history: bool = True):
        """Navigate to a screen and update history"""
        if add_to_history and self.current_screen:
            self.history.append(self.current_screen)
        
        self.current_screen = screen_name
        self.app.show_screen(screen_name)
    
    def go_back(self):
        """Go back to previous screen"""
        if self.history:
            previous_screen = self.history.pop()
            self.navigate_to(previous_screen, add_to_history=False)
            return True
        return False
    
    def get_breadcrumb_path(self, screen_name: str = None) -> List[Dict[str, Any]]:
        """Get breadcrumb path for current or specified screen"""
        target_screen = screen_name or self.current_screen
        if not target_screen or target_screen not in self.screen_hierarchy:
            return []
        
        path = []
        current = target_screen
        
        while current:
            screen_info = self.screen_hierarchy[current]
            path.insert(0, {
                'label': screen_info['label'],
                'screen_name': current,
                'icon': screen_info.get('icon')
            })
            current = screen_info.get('parent')
        
        return path
    
    def clear_history(self):
        """Clear navigation history"""
        self.history.clear()
