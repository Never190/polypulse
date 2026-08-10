def section_header(layout, props, prop_name, label, icon='NONE'):
    state = bool(getattr(props, prop_name, True))
    tri_icon = 'DISCLOSURE_TRI_DOWN' if state else 'DISCLOSURE_TRI_RIGHT'
    header = layout.row(align=True)
    header.prop(props, prop_name, icon=tri_icon, icon_only=True, emboss=
        False, text='')
    header.prop(props, prop_name, icon=icon, emboss=False, text=label)
    return state
