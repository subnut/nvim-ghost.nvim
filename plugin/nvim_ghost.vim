let g:nvim_ghost_debounce = get(g:,'nvim_ghost_debounce', 200)
let g:nvim_ghost_binary_path  =  expand('<sfile>:h:h') . (has('win32') ? '/binary.exe' :  '/binary')

if !filereadable(g:nvim_ghost_binary_path )
	echohl ErrorMsg
	echom 'nvim-ghost binary not readable'
	echohl None
	finish
endif

call jobstart(g:nvim_ghost_binary_path  . ' --start-server', {'on_stdout':{j,d,e->execute('echom  "nvim-ghost:" "' . d[0] . '"')}})
au UIEnter,FocusGained * call nvim_ghost#request_focus()
