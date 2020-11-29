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

let s:joblog_arguments = {'on_stdout':{id,data,type->nvim_ghost#joboutput_logger(data,type)}, 'on_stderr':{id,data,type->nvim_ghost#joboutput_logger(data,type)}}

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
	let l:job = jobstart(g:nvim_ghost_binary_path  . l:arguments, s:joblog_arguments)
	call chansend(l:job, getbufline(a:bufnr,1,'$'))
	call chanclose(l:job)
endfun

fun! nvim_ghost#request_focus()
	call jobstart(g:nvim_ghost_binary_path  . ' --focus ' . $NVIM_LISTEN_ADDRESS)
endfun

fun! nvim_ghost#notify_buffer_deleted(bufnr)
	call nvim_ghost#request_focus()
	let l:arguments = ' --buffer-closed ' . a:bufnr
	let l:job = jobstart(g:nvim_ghost_binary_path  . l:arguments, s:joblog_arguments)
endfun

fun! nvim_ghost#setup_buffer_autocmds(bufnr)
	exe 'augroup nvim_ghost_' . a:bufnr
	exe 'au nvim_ghost_'.a:bufnr.' TextChanged,TextChangedI,TextChangedP <buffer='.a:bufnr.'> call nvim_ghost#update_buffer('.a:bufnr.')'
	exe 'au nvim_ghost_'.a:bufnr.' BufDelete <buffer='.a:bufnr.'> call nvim_ghost#notify_buffer_deleted('.a:bufnr.')'
	exe 'augroup END'
endfun

fun! nvim_ghost#delete_buffer_autocmds(bufnr)
	exe 'augroup nvim_ghost_' . a:bufnr
	exe 'au! nvim_ghost_'.a:bufnr
	exe 'augroup END'
endfun

function nvim_ghost#joboutput_logger(data,type)
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
