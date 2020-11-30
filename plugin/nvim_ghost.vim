let g:nvim_ghost_debounce = get(g:,'nvim_ghost_debounce', 200)
let g:nvim_ghost_binary_path  =  expand('<sfile>:h:h') . (has('win32') ? '\binary.exe' :  '/binary')
let g:nvim_ghost_logging_enabled = get(g:,'nvim_ghost_logging_enabled', 0)

if !filereadable(g:nvim_ghost_binary_path)
	echohl ErrorMsg
	echom 'nvim-ghost binary not readable'
	echohl None
	finish
endif

au UIEnter,FocusGained * call nvim_ghost#start_server()
au UIEnter,FocusGained * call nvim_ghost#request_focus()

let g:_nvim_ghost_supports_focus = 0
au FocusGained,FocusLost * ++once
			\  let g:_nvim_ghost_supports_focus = 1
			\| call nvim_ghost#_can_use_cursorhold()
			\| au! _nvim_ghost_does_not_support_focus

augroup _nvim_ghost_does_not_support_focus
	au CursorMoved,CursorMovedI * call s:focus_gained()
	au CursorHold,CursorHoldI * let s:focused = v:false
augroup END

let s:focused = v:true
fun! s:focus_gained()
	if !s:focused
		call nvim_ghost#request_focus()
		let s:focused = v:true
	endif
endfun
