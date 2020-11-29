if exists('g:loaded_nvim_ghost')
	finish
endif
let g:loaded_nvim_ghost = 1

let g:nvim_ghost#debounce = get(g:,'g:nvim_ghost#debounce', 200)

let s:binary_path =  expand('<sfile>:h:h') . (has('win32') ? '/binary.exe' :  '/binary')

if !filereadable(s:binary_path)
	echohl ErrorMsg
	echom 'nvim-ghost binary not readable'
	echohl None
	finish
endif

fun! nvim_ghost#update_buffer(bufnr)
	let l:timer = nvim_buf_get_var(a:bufnr,'nvim_ghost_timer')
	if l:timer
		call timer_stop(l:timer)
	endif
	let l:timer = timer_start(g:nvim_ghost#debounce, {->execute('call nvim_ghost#send_buffer(' . a:bufnr . ')')})
	call nvim_buf_set_var(a:bufnr,'nvim_ghost_timer',l:timer)
endfunction

fun! nvim_ghost#send_buffer(bufnr)
	call nvim_ghost#request_focus()
	let l:arguments = ' --update-buffer-text ' . a:bufnr
	let l:job = jobstart(s:binary_path . l:arguments, {'on_stdout':{j,d,e->execute('echom  "nvim-ghost:" "' . d[0] . '"')}})
	call chansend(l:job, getbufline(a:bufnr,1,'$'))
	call chanclose(l:job)
endfun

fun! nvim_ghost#request_focus()
	call jobstart(s:binary_path . ' --focus ' . $NVIM_LISTEN_ADDRESS)
endfun

fun! nvim_ghost#notify_buffer_deleted(bufnr)
	let l:text = join(getbufline(a:bufnr,1,'$'),'\n')
	call nvim_ghost#request_focus()
	let l:arguments = ' --buffer-closed ' . a:bufnr
	let l:job = jobstart(s:binary_path . l:arguments, {'on_stdout':{j,d,e->execute('echom  "nvim-ghost:" "' . d[0] . '"')}})
endfun
