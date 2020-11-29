if exists('g:loaded_nvim_ghost')
	finish
endif
let g:loaded_nvim_ghost = 1

let g:nvim_ghost#debounce = get(g:,'g:nvim_ghost#debounce', 200)

fun! nvim_ghost#update_buffer(bufnr)
	let l:timer = nvim_buf_get_var(a:bufnr,'nvim_ghost_timer')
	if l:timer
		call timer_stop(l:timer)
	endif
	let l:timer = timer_start(g:nvim_ghost#debounce, {->execute('silent! call nvim_ghost#send_buffer(' . a:bufnr . ')')})
	call nvim_buf_set_var(a:bufnr,'nvim_ghost_timer',l:timer)
endfunction

fun! nvim_ghost#send_buffer(bufnr)
	let l:text = join(getbufline(a:bufnr,1,'$'),'\n')
	let l:send_prefix = ' --update-buffer-text ' . a:bufnr
	let l:focustext = ' --focus ' . $NVIM_LISTEN_ADDRESS
	let l:binary = 'python ' . expand('<sfile>:h:h') . '/binary.py'
	exe '!echo -n ' . shellescape(l:text, v:true) . ' | ' . l:binary . l:send_prefix
	exe '!' . l:binary . l:focustext
endfun

fun! nvim_ghost#notify_buffer_deleted(bufnr)
	let l:text = join(getbufline(a:bufnr,1,'$'),'\n')
	let l:binary = 'python ' . expand('<sfile>:h:h') . '/binary.py'
	let l:focustext = ' --focus ' . $NVIM_LISTEN_ADDRESS
	let l:deletetext = ' --buffer-closed ' . a:bufnr
	exe '!' . l:binary . l:focustext
	exe '!' . l:binary . l:deletetext
endfun
