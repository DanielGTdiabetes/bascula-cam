# -*- coding: utf-8 -*-
"""
Enhanced TopBar with modern navigation features
Extends the original TopBar with breadcrumbs and navigation drawer
"""

import tkinter as tk
from bascula.config.theme import get_current_colors
from bascula.ui.widgets import get_scaled_size, FS_TEXT, Mascot
from bascula.ui.navigation import Breadcrumb, NavigationDrawer

# Get theme colors
pal = get_current_colors()
COL_BG = pal['COL_BG']
COL_CARD = pal['COL_CARD']
COL_TEXT = pal['COL_TEXT']
COL_ACCENT = pal['COL_ACCENT']
COL_MUTED = pal['COL_MUTED']


class EnhancedTopBar(tk.Frame):
    """Enhanced TopBar with breadcrumbs and navigation drawer"""
    
    def __init__(self, parent, app, navigation_manager=None, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.app = app
        self.navigation_manager = navigation_manager
        
        # Main topbar height
        topbar_height = get_scaled_size(60)
        self.configure(height=topbar_height)
        self.pack_propagate(False)
        
        # Top row - original topbar content
        self.top_row = tk.Frame(self, bg=COL_CARD, height=topbar_height)
        self.top_row.pack(fill='x')
        self.top_row.pack_propagate(False)
        
        # Left side - Navigation button and mascot
        self.left_frame = tk.Frame(self.top_row, bg=COL_CARD)
        self.left_frame.pack(side='left', fill='y')
        
        # Navigation menu button (hamburger)
        self.nav_button = tk.Button(self.left_frame, text='☰', 
                                   command=self._toggle_navigation,
                                   bg=COL_CARD, fg=COL_TEXT, bd=0, relief='flat',
                                   font=("DejaVu Sans", FS_TEXT), cursor="hand2",
                                   width=3, height=2)
        self.nav_button.pack(side='left', padx=(get_scaled_size(8), get_scaled_size(4)))
        
        # Mascot
        self.mascot = Mascot(self.left_frame, width=get_scaled_size(60), 
                           height=get_scaled_size(60), bg=COL_CARD)
        self.mascot.pack(side='left', padx=get_scaled_size(6))
        
        # Center - Message and breadcrumbs area
        self.center_frame = tk.Frame(self.top_row, bg=COL_CARD)
        self.center_frame.pack(side='left', fill='both', expand=True, padx=get_scaled_size(8))
        
        # Message label (top priority)
        self.msg = tk.Label(self.center_frame, text='', bg=COL_CARD, fg=COL_TEXT,
                           font=("DejaVu Sans", FS_TEXT, 'bold'))
        self.msg.pack(side='top', anchor='w')
        
        # Breadcrumb container (shows when no message)
        self.breadcrumb_container = tk.Frame(self.center_frame, bg=COL_CARD)
        self.breadcrumb = Breadcrumb(self.breadcrumb_container, 
                                   navigation_callback=self._navigate_from_breadcrumb)
        self.breadcrumb.pack(fill='x')
        
        # Right side - Status indicators
        self.right_frame = tk.Frame(self.top_row, bg=COL_CARD)
        self.right_frame.pack(side='right', fill='y')
        
        # Timer label
        self._timer_label = tk.Label(self.right_frame, text='', bg=COL_CARD, fg=COL_TEXT,
                                   font=("DejaVu Sans", FS_TEXT, 'bold'))
        
        # Sound button
        self.sound_btn = tk.Button(self.right_frame, text='🔊', 
                                 command=self.app.toggle_sound,
                                 bg=COL_CARD, fg=COL_TEXT, bd=0, relief='flat',
                                 font=("DejaVu Sans", FS_TEXT), cursor="hand2")
        self.sound_btn.pack(side='right', padx=get_scaled_size(4))
        
        # WiFi indicator
        self.wifi_lbl = tk.Label(self.right_frame, text='📶', bg=COL_CARD, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TEXT))
        self.wifi_lbl.pack(side='right', padx=get_scaled_size(4))
        
        # Blood glucose indicator
        self.bg_lbl = tk.Label(self.right_frame, text='', bg=COL_CARD, fg=COL_TEXT,
                             font=("DejaVu Sans", FS_TEXT))
        self.bg_lbl.pack(side='right', padx=get_scaled_size(4))
        
        # Navigation drawer
        self.nav_drawer = NavigationDrawer(parent, width=get_scaled_size(280))
        self.nav_drawer.navigation_callback = self._navigate_from_drawer
        self._setup_navigation_items()
        
        # State
        self.current_message = ''
        self.showing_breadcrumbs = False
    
    def _setup_navigation_items(self):
        """Setup navigation drawer items"""
        nav_items = [
            {'label': 'Inicio', 'screen_name': 'home', 'icon': '🏠'},
            {'label': 'Báscula', 'screen_name': 'scale', 'icon': '⚖️'},
            {'label': 'Escáner', 'screen_name': 'scanner', 'icon': '📷'},
            {'label': 'Ajustes', 'screen_name': 'settingsmenu', 'icon': '⚙️'},
        ]
        
        for item in nav_items:
            self.nav_drawer.add_nav_item(
                label=item['label'],
                screen_name=item['screen_name'],
                icon=item['icon']
            )
    
    def _toggle_navigation(self):
        """Toggle navigation drawer"""
        self.nav_drawer.toggle()
    
    def _navigate_from_breadcrumb(self, screen_name: str):
        """Handle navigation from breadcrumb"""
        if self.navigation_manager:
            self.navigation_manager.navigate_to(screen_name)
        else:
            self.app.show_screen(screen_name)
    
    def _navigate_from_drawer(self, screen_name: str):
        """Handle navigation from drawer"""
        if self.navigation_manager:
            self.navigation_manager.navigate_to(screen_name)
        else:
            self.app.show_screen(screen_name)
    
    def update_breadcrumbs(self, screen_name: str = None):
        """Update breadcrumb display"""
        if not self.navigation_manager or self.current_message:
            return
        
        path = self.navigation_manager.get_breadcrumb_path(screen_name)
        if path and len(path) > 1:  # Only show breadcrumbs if there's a path
            self.breadcrumb.set_path(path)
            if not self.showing_breadcrumbs:
                self.breadcrumb_container.pack(side='top', anchor='w', fill='x')
                self.showing_breadcrumbs = True
        else:
            if self.showing_breadcrumbs:
                self.breadcrumb_container.pack_forget()
                self.showing_breadcrumbs = False
    
    def set_message(self, text: str) -> None:
        """Set message text (takes priority over breadcrumbs)"""
        self.current_message = text
        self.msg.config(text=text)
        
        if text:
            # Hide breadcrumbs when showing message
            if self.showing_breadcrumbs:
                self.breadcrumb_container.pack_forget()
                self.showing_breadcrumbs = False
        else:
            # Show breadcrumbs when no message
            self.update_breadcrumbs()
    
    def set_timer(self, text: str):
        """Show/hide timer in the topbar"""
        if not hasattr(self, "_timer_label"):
            return
        
        if not text:
            # Hide timer
            try:
                self._timer_label.config(text="")
                self._timer_label.pack_forget()
            except Exception:
                pass
            return
        
        # Show timer
        try:
            if not self._timer_label.winfo_ismapped():
                self._timer_label.pack(side="right", padx=get_scaled_size(8))
            self._timer_label.config(text=str(text))
        except Exception:
            pass
    
    def set_bg(self, value: str = None, trend: str = '') -> None:
        """Set blood glucose display"""
        if value is None:
            self.bg_lbl.config(text='')
        else:
            arrow = {'up': '↑', 'down': '↓', 'flat': '→'}.get(trend, trend)
            self.bg_lbl.config(text=f'{value}{arrow}')
    
    def set_wifi(self, text: str) -> None:
        """Set WiFi status"""
        self.wifi_lbl.config(text=text)
    
    def set_navigation_manager(self, navigation_manager):
        """Set the navigation manager"""
        self.navigation_manager = navigation_manager
        self.nav_drawer.navigation_callback = self._navigate_from_drawer
