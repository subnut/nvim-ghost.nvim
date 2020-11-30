if exists('g:loaded_nvim_ghost')
	finish
endif
let g:loaded_nvim_ghost = 1

if !filereadable(g:nvim_ghost_binary_path )
	echohl ErrorMsg
	echom 'nvim-ghost binary not readable'
	echohl None
	finish
endif

let s:saved_updatetime = &updatetime
let s:can_use_cursorhold = v:false
let s:joblog_arguments = {
			\'on_stdout':{id,data,type->nvim_ghost#joboutput_logger(data,type)},
			\'on_stderr':{id,data,type->nvim_ghost#joboutput_logger(data,type)}
			\}
let s:bufnr_list = []

fun! nvim_ghost#start_server()
	call jobstart(shellescape(g:nvim_ghost_binary_path)  . ' --start-server', s:joblog_arguments)
endfun

fun! nvim_ghost#update_buffer(bufnr)
	let l:timer = nvim_buf_get_var(a:bufnr,'nvim_ghost_timer')
	if l:timer
		call timer_stop(l:timer)
	endif
	let l:timer = timer_start(g:nvim_ghost_debounce, {->execute('call nvim_ghost#send_buffer('.a:bufnr.')')})
	call nvim_buf_set_var(a:bufnr,'nvim_ghost_timer',l:timer)
endfunction

fun! nvim_ghost#send_buffer(bufnr)
	call nvim_ghost#request_focus()
	let l:arguments = ' --update-buffer-text ' . a:bufnr
	let l:job = jobstart(shellescape(g:nvim_ghost_binary_path)  . l:arguments, s:joblog_arguments)
	call chansend(l:job, getbufline(a:bufnr,1,'$'))
	call chanclose(l:job)
endfun

fun! nvim_ghost#request_focus()
	call jobstart(shellescape(g:nvim_ghost_binary_path)  . ' --focus ' . $NVIM_LISTEN_ADDRESS)
endfun

fun! nvim_ghost#notify_buffer_deleted(bufnr)
	call nvim_ghost#request_focus()
	let l:arguments = ' --buffer-closed ' . a:bufnr
	let l:job = jobstart(shellescape(g:nvim_ghost_binary_path)  . l:arguments, s:joblog_arguments)
endfun

fun! nvim_ghost#setup_buffer_autocmds(bufnr)
	if count(s:bufnr_list, a:bufnr) == 0
		call extend(s:bufnr_list, [a:bufnr])
	endif
	exe 'augroup nvim_ghost_' . a:bufnr
	if !s:can_use_cursorhold
		exe 'au nvim_ghost_'.a:bufnr.' TextChanged,TextChangedI,TextChangedP <buffer='.a:bufnr.'> call nvim_ghost#update_buffer('.a:bufnr.')'
	else
		exe 'au nvim_ghost_'.a:bufnr.' CursorHold,CursorHoldI <buffer='.a:bufnr.'> call nvim_ghost#send_buffer('.a:bufnr.')'
		exe 'au nvim_ghost_'.a:bufnr.' BufEnter <buffer='.a:bufnr.'> call nvim_ghost#_buffer_enter()'
		exe 'au nvim_ghost_'.a:bufnr.' BufLeave <buffer='.a:bufnr.'> call nvim_ghost#_buffer_leave()'
	endif
	exe 'au nvim_ghost_'.a:bufnr.' BufDelete <buffer='.a:bufnr.'> call nvim_ghost#notify_buffer_deleted('.a:bufnr.')'
	exe 'augroup END'
endfun

fun! nvim_ghost#delete_buffer_autocmds(bufnr)
	exe 'augroup nvim_ghost_' . a:bufnr
	exe 'au! nvim_ghost_'.a:bufnr
	exe 'augroup END'
endfun

fun! nvim_ghost#joboutput_logger(data,type)
	if !g:nvim_ghost_logging_enabled
		return
	endif
	if a:type ==# 'stderr'
		echohl WarningMsg
	endif
	for line in a:data
		if len(line) == 0
			continue
		endif
		echom '[nvim-ghost] ' . a:type . ': ' . line
	endfor
	if a:type ==# 'stderr'
		echohl None
	endif
endfun

fun! nvim_ghost#_can_use_cursorhold()
	let s:can_use_cursorhold = v:true
	for bufnr in s:bufnr_list
		call nvim_ghost#delete_buffer_autocmds(bufnr)
		call nvim_ghost#setup_buffer_autocmds(bufnr)
	endfor
endfun

fun! nvim_ghost#_buffer_enter()
	let s:saved_updatetime = &updatetime
	let &updatetime = g:nvim_ghost_updatetime
endfun

fun! nvim_ghost#_buffer_leave()
	let &updatetime = s:saved_updatetime
endfun
