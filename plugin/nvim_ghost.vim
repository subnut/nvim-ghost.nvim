let g:nvim_ghost_debounce = get(g:,'nvim_ghost_debounce', 200)
let g:nvim_ghost_binary_path  =  expand('<sfile>:h:h') . (has('win32') ? '\binary.exe' :  '/binary')
let g:nvim_ghost_logging_enabled = get(g:,'nvim_ghost_logging_enabled', 0)

if !filereadable(g:nvim_ghost_binary_path)
	echohl ErrorMsg
	echom 'nvim-ghost binary not readable'
	echohl None
	finish
endif

au UIEnter,FocusGained * call jobstart(g:nvim_ghost_binary_path  . ' --start-server', {'on_stdout':{id,data,type->nvim_ghost#joboutput_logger(data,type)}, 'on_stderr':{id,data,type->nvim_ghost#joboutput_logger(data,type)}})
au UIEnter,FocusGained * call nvim_ghost#request_focus()
