class SettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con navegación por pestañas"""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        
        # Header principal
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header, text="⚙", bg=COL_BG, fg=COL_ACCENT,
                font=("DejaVu Sans", 28)).pack(side="left")
        tk.Label(header, text="Configuración", bg=COL_BG, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=10)
        
        # Botón volver
        back_btn = tk.Button(header, text="← Volver", command=lambda: self.app.show_screen('home'),
                           bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL),
                           bd=0, relief="flat", cursor="hand2")
        back_btn.pack(side="right")
        
        # Container principal con pestañas
        main_container = Card(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Notebook para pestañas
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Estilo para las pestañas
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Settings.TNotebook', background=COL_CARD, borderwidth=0)
        style.configure('Settings.TNotebook.Tab',
                       background=COL_CARD,
                       foreground=COL_TEXT,
                       padding=[20, 10],
                       font=("DejaVu Sans", FS_TEXT))
        style.map('Settings.TNotebook.Tab',
                 background=[('selected', COL_ACCENT)],
                 foreground=[('selected', 'white')])
        
        # Crear pestañas
        self._create_general_tab()
        self._create_scale_tab()
        self._create_network_tab()
        self._create_diabetes_tab()
        self._create_storage_tab()
        self._create_about_tab()
        
        self.toast = Toast(self)
    
    def _create_general_tab(self):
        """Pestaña de configuración general"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="🎯 General")
        
        scroll_frame = tk.Frame(tab, bg=COL_CARD)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        # === Sección: Interfaz ===
        self._add_section_header(scroll_frame, "Interfaz de Usuario")
        
        # Sonido
        sound_frame = self._create_option_row(scroll_frame)
        tk.Label(sound_frame, text="Sonido:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_sound = tk.BooleanVar(value=self.app.get_cfg().get('sound_enabled', True))
        sound_check = ttk.Checkbutton(sound_frame, text="Activado", variable=self.var_sound,
                                     command=self._toggle_sound)
        sound_check.pack(side="left")
        
        # Tema de sonido
        self.var_theme = tk.StringVar(value=self.app.get_cfg().get('sound_theme', 'beep'))
        theme_combo = ttk.Combobox(sound_frame, textvariable=self.var_theme,
                                  values=["beep", "voice_es"], width=10, state="readonly")
        theme_combo.pack(side="left", padx=(20, 10))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_sound_theme())
        
        test_btn = tk.Button(sound_frame, text="Probar", command=self._test_sound,
                           bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_TEXT),
                           bd=0, relief="flat", cursor="hand2", padx=15)
        test_btn.pack(side="left")
        
        # Decimales
        decimal_frame = self._create_option_row(scroll_frame)
        tk.Label(decimal_frame, text="Decimales en peso:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_decimals = tk.IntVar(value=self.app.get_cfg().get('decimals', 0))
        for i in range(3):
            rb = ttk.Radiobutton(decimal_frame, text=str(i), variable=self.var_decimals,
                               value=i, command=self._apply_decimals)
            rb.pack(side="left", padx=5)
        
        # === Sección: Unidades ===
        self._add_section_header(scroll_frame, "Unidades", top_pad=30)
        
        unit_frame = self._create_option_row(scroll_frame)
        tk.Label(unit_frame, text="Unidad de peso:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_unit = tk.StringVar(value=self.app.get_cfg().get('unit', 'g'))
        ttk.Radiobutton(unit_frame, text="Gramos (g)", variable=self.var_unit,
                       value="g", command=self._apply_unit).pack(side="left", padx=5)
        ttk.Radiobutton(unit_frame, text="Kilogramos (kg)", variable=self.var_unit,
                       value="kg", command=self._apply_unit).pack(side="left", padx=5)
    
    def _create_scale_tab(self):
        """Pestaña de configuración de báscula"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="⚖ Báscula")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # === Sección: Calibración ===
        self._add_section_header(content, "Calibración")
        
        cal_info = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        cal_info.pack(fill="x", pady=10)
        cal_info_inner = tk.Frame(cal_info, bg="#1a1f2e")
        cal_info_inner.pack(padx=15, pady=10)
        
        tk.Label(cal_info_inner, text="Factor actual:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        self.cal_factor_label = tk.Label(cal_info_inner, 
                                        text=f"{self.app.get_cfg().get('calib_factor', 1.0):.6f}",
                                        bg="#1a1f2e", fg=COL_ACCENT,
                                        font=("DejaVu Sans Mono", FS_TEXT, "bold"))
        self.cal_factor_label.grid(row=0, column=1, sticky="w", padx=20, pady=2)
        
        tk.Label(cal_info_inner, text="Puerto serie:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(cal_info_inner, text=self.app.get_cfg().get('port', '/dev/serial0'),
                bg="#1a1f2e", fg=COL_MUTED,
                font=("DejaVu Sans Mono", FS_TEXT)).grid(row=1, column=1, sticky="w", padx=20, pady=2)
        
        cal_btn = tk.Button(content, text="⚖ Iniciar Calibración",
                          command=lambda: self.app.show_screen('calib'),
                          bg=COL_ACCENT, fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                          bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        cal_btn.pack(pady=10)
        
        # === Sección: Filtrado ===
        self._add_section_header(content, "Filtrado de Señal", top_pad=30)
        
        smooth_frame = self._create_option_row(content)
        tk.Label(smooth_frame, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_smoothing = tk.IntVar(value=self.app.get_cfg().get('smoothing', 5))
        smooth_scale = ttk.Scale(smooth_frame, from_=1, to=20,
                               variable=self.var_smoothing, orient="horizontal",
                               length=200, command=lambda v: self._apply_smoothing())
        smooth_scale.pack(side="left", padx=10)
        
        self.smooth_label = tk.Label(smooth_frame, text=str(self.var_smoothing.get()),
                                    bg=COL_CARD, fg=COL_ACCENT,
                                    font=("DejaVu Sans", FS_TEXT, "bold"))
        self.smooth_label.pack(side="left", padx=5)
    
    def _create_network_tab(self):
        """Pestaña de configuración de red"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="📡 Red")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # === Sección: Estado de Red ===
        self._add_section_header(content, "Estado de Conexión")
        
        status_frame = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        status_frame.pack(fill="x", pady=10)
        status_inner = tk.Frame(status_frame, bg="#1a1f2e")
        status_inner.pack(padx=15, pady=10)
        
        # Detectar IP actual
        ip = self._get_current_ip()
        
        tk.Label(status_inner, text="IP Local:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(status_inner, text=ip if ip else "No conectado",
                bg="#1a1f2e", fg=(COL_SUCCESS if ip else COL_WARN),
                font=("DejaVu Sans Mono", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        # === Sección: Mini-Web ===
        self._add_section_header(content, "Panel Web", top_pad=20)
        
        web_frame = self._create_option_row(content)
        tk.Label(web_frame, text="URL:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        url = f"http://{ip if ip else 'localhost'}:8080"
        url_label = tk.Label(web_frame, text=url, bg=COL_CARD, fg=COL_ACCENT,
                           font=("DejaVu Sans Mono", FS_TEXT))
        url_label.pack(side="left")
        
        # PIN
        pin_frame = self._create_option_row(content)
        tk.Label(pin_frame, text="PIN:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        pin = self._read_pin()
        self.pin_label = tk.Label(pin_frame, text=pin, bg=COL_CARD, fg=COL_ACCENT,
                                 font=("DejaVu Sans Mono", FS_TEXT, "bold"))
        self.pin_label.pack(side="left", padx=(0, 20))
        
        refresh_btn = tk.Button(pin_frame, text="Actualizar", command=self._refresh_network,
                              bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                              bd=0, relief="flat", cursor="hand2", padx=15)
        refresh_btn.pack(side="left")
        
        # QR Code si está disponible
        if _QR_OK and ip:
            qr_frame = tk.Frame(content, bg=COL_CARD)
            qr_frame.pack(pady=20)
            
            try:
                qr = qrcode.QRCode(border=1, box_size=3)
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                img = img.resize((150, 150))
                photo = ImageTk.PhotoImage(img)
                
                qr_label = tk.Label(qr_frame, image=photo, bg=COL_CARD)
                qr_label.image = photo  # Keep reference
                qr_label.pack()
                
                tk.Label(qr_frame, text="Escanea para acceder desde el móvil",
                        bg=COL_CARD, fg=COL_MUTED,
                        font=("DejaVu Sans", FS_TEXT-1)).pack(pady=(5, 0))
            except:
                pass
        
        # Botones de configuración
        btn_frame = tk.Frame(content, bg=COL_CARD)
        btn_frame.pack(pady=20)
        
        wifi_btn = tk.Button(btn_frame, text="📶 Configurar Wi-Fi",
                           command=lambda: self.app.show_screen('wifi'),
                           bg="#3b82f6", fg="white",
                           font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                           bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        wifi_btn.pack(side="left", padx=5)
        
        api_btn = tk.Button(btn_frame, text="🔑 API Key",
                          command=lambda: self.app.show_screen('apikey'),
                          bg="#6b7280", fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                          bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        api_btn.pack(side="left", padx=5)
    
    def _create_diabetes_tab(self):
        """Pestaña de configuración para diabéticos"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="💉 Diabetes")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # === Modo Diabético ===
        self._add_section_header(content, "Modo Diabético")
        
        dm_frame = self._create_option_row(content)
        self.var_dm = tk.BooleanVar(value=self.app.get_cfg().get('diabetic_mode', False))
        dm_check = ttk.Checkbutton(dm_frame, text="Activar modo diabético (experimental)",
                                  variable=self.var_dm, command=self._toggle_dm)
        dm_check.pack(side="left")
        
        tk.Label(dm_frame, text="⚠ No es consejo médico", bg=COL_CARD, fg=COL_WARN,
                font=("DejaVu Sans", FS_TEXT-1)).pack(side="left", padx=20)
        
        # === Nightscout ===
        self._add_section_header(content, "Nightscout", top_pad=30)
        
        ns_info = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        ns_info.pack(fill="x", pady=10)
        ns_inner = tk.Frame(ns_info, bg="#1a1f2e")
        ns_inner.pack(padx=15, pady=10)
        
        # Check Nightscout status
        ns_configured = self._check_nightscout()
        
        tk.Label(ns_inner, text="Estado:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(ns_inner, text="Configurado" if ns_configured else "No configurado",
                bg="#1a1f2e", fg=(COL_SUCCESS if ns_configured else COL_WARN),
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        ns_btn = tk.Button(content, text="⚙ Configurar Nightscout",
                         command=lambda: self.app.show_screen('nightscout'),
                         bg=COL_ACCENT, fg="white",
                         font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                         bd=0, relief="flat", cursor="hand2", padx=20, pady=10,
                         state=("normal" if self.var_dm.get() else "disabled"))
        ns_btn.pack(pady=10)
        self.ns_config_btn = ns_btn
        
        # === Parámetros de Bolo ===
        self._add_section_header(content, "Parámetros de Bolo", top_pad=30)
        
        params_frame = tk.Frame(content, bg=COL_CARD)
        params_frame.pack(fill="x", pady=10)
        
        # Grid de parámetros
        params = [
            ("Objetivo (mg/dL)", 'target_bg_mgdl', 110),
            ("ISF (mg/dL/U)", 'isf_mgdl_per_u', 50),
            ("Ratio HC (g/U)", 'carb_ratio_g_per_u', 10),
            ("DIA (horas)", 'dia_hours', 4),
        ]
        
        self.param_vars = {}
        for i, (label, key, default) in enumerate(params):
            row = i // 2
            col = i % 2
            
            frame = tk.Frame(params_frame, bg=COL_CARD)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="w")
            
            tk.Label(frame, text=label, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")
            
            var = tk.StringVar(value=str(self.app.get_cfg().get(key, default)))
            entry = tk.Entry(frame, textvariable=var, width=10,
                           bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                           relief="flat", bd=5)
            entry.pack(anchor="w", pady=2)
            
            self.param_vars[key] = var
        
        save_params_btn = tk.Button(content, text="💾 Guardar Parámetros",
                                   command=self._save_diabetes_params,
                                   bg="#3b82f6", fg="white",
                                   font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                                   bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        save_params_btn.pack(pady=10)
    
    def _create_storage_tab(self):
        """Pestaña de almacenamiento y datos"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="💾 Datos")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # === Histórico de Comidas ===
        self._add_section_header(content, "Histórico de Comidas")
        
        hist_frame = tk.Frame(content, bg=COL_CARD)
        hist_frame.pack(fill="x", pady=10)
        
        # Estadísticas
        stats_frame = tk.Frame(hist_frame, bg="#1a1f2e", relief="ridge", bd=1)
        stats_frame.pack(fill="x", pady=5)
        stats_inner = tk.Frame(stats_frame, bg="#1a1f2e")
        stats_inner.pack(padx=15, pady=10)
        
        meals_path = Path.home() / '.config' / 'bascula' / 'meals.jsonl'
        if meals_path.exists():
            size = meals_path.stat().st_size
            try:
                with open(meals_path, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
            except:
                count = 0
        else:
            size = 0
            count = 0
        
        tk.Label(stats_inner, text="Entradas:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(stats_inner, text=str(count), bg="#1a1f2e", fg=COL_ACCENT,
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        tk.Label(stats_inner, text="Tamaño:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(stats_inner, text=f"{size/1_000_000:.2f} MB", bg="#1a1f2e", fg=COL_ACCENT,
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=1, column=1, padx=20, pady=2)
        
        # Configuración de retención
        ret_frame = tk.Frame(content, bg=COL_CARD)
        ret_frame.pack(fill="x", pady=10)
        
        tk.Label(ret_frame, text="Retención:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT, "bold")).pack(anchor="w", pady=5)
        
        ret_grid = tk.Frame(ret_frame, bg=COL_CARD)
        ret_grid.pack(fill="x")
        
        self.ret_vars = {}
        ret_params = [
            ("Días máximo", 'meals_max_days', 180),
            ("Entradas máximo", 'meals_max_entries', 1000),
            ("Tamaño máximo (MB)", 'meals_max_bytes', 5),
        ]
        
        for i, (label, key, default) in enumerate(ret_params):
            frame = tk.Frame(ret_grid, bg=COL_CARD)
            frame.grid(row=i//2, column=i%2, padx=10, pady=5, sticky="w")
            
            tk.Label(frame, text=label, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            
            val = default if key != 'meals_max_bytes' else self.app.get_cfg().get(key, default*1_000_000)//1_000_000
            var = tk.StringVar(value=str(val))
            entry = tk.Entry(frame, textvariable=var, width=8,
                           bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                           relief="flat", bd=3)
            entry.pack(side="left", padx=10)
            
            self.ret_vars[key] = var
        
        # Botones de acción
        action_frame = tk.Frame(content, bg=COL_CARD)
        action_frame.pack(pady=15)
        
        apply_btn = tk.Button(action_frame, text="Aplicar Retención",
                            command=self._apply_retention,
                            bg="#3b82f6", fg="white",
                            font=("DejaVu Sans", FS_BTN_SMALL),
                            bd=0, relief="flat", cursor="hand2", padx=15, pady=8)
        apply_btn.pack(side="left", padx=5)
        
        clear_btn = tk.Button(action_frame, text="Limpiar Histórico",
                            command=self._clear_history,
                            bg=COL_DANGER, fg="white",
                            font=("DejaVu Sans", FS_BTN_SMALL),
                            bd=0, relief="flat", cursor="hand2", padx=15, pady=8)
        clear_btn.pack(side="left", padx=5)
        
        # === Fotos ===
        self._add_section_header(content, "Fotos Temporales", top_pad=30)
        
        photos_frame = self._create_option_row(content)
        self.var_keep_photos = tk.BooleanVar(value=self.app.get_cfg().get('keep_photos', False))
        photos_check = ttk.Checkbutton(photos_frame, 
                                      text="Mantener fotos entre reinicios",
                                      variable=self.var_keep_photos,
                                      command=self._apply_keep_photos)
        photos_check.pack(side="left")
        
        clear_photos_btn = tk.Button(photos_frame, text="Limpiar Fotos",
                                    command=self._clear_photos,
                                    bg=COL_DANGER, fg="white",
                                    font=("DejaVu Sans", FS_TEXT),
                                    bd=0, relief="flat", cursor="hand2", padx=15)
        clear_photos_btn.pack(side="right")
    
    def _create_about_tab(self):
        """Pestaña de información"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="ℹ Acerca de")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Logo y título
        title_frame = tk.Frame(content, bg=COL_CARD)
        title_frame.pack(pady=20)
        
        tk.Label(title_frame, text="⚖", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", 48)).pack()
        tk.Label(title_frame, text="Báscula Digital Pro", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TITLE+2, "bold")).pack(pady=(10, 5))
        tk.Label(title_frame, text="v1.0.0", bg=COL_CARD, fg=COL_MUTED,
                font=("DejaVu Sans", FS_TEXT)).pack()
        
        # Info
        info_frame =
