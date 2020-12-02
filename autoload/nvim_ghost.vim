if !has('nvim')
  finish
endif

if exists('g:loaded_nvim_ghost')
  finish
endif
let g:loaded_nvim_ghost = 1

let s:saved_updatetime = &updatetime
let s:can_use_cursorhold = v:false
let s:joblog_arguments = {
      \'on_stdout':{id,data,type->nvim_ghost#joboutput_logger(data,type)},
      \'on_stderr':{id,data,type->nvim_ghost#joboutput_logger(data,type)}
      \}
let s:bufnr_list = []

function! nvim_ghost#start_server() abort " {{{1
  if has('win32')
    call systemlist(['cscript.exe', g:nvim_ghost_script_path.'\start_server.vbs'])
  else
    call systemlist([g:nvim_ghost_script_path.'/start_server.sh'])
  endif
endfunction

function! nvim_ghost#kill_server() abort  " {{{1
  call jobstart([g:nvim_ghost_binary_path, '--kill'], s:joblog_arguments)
endfunction

function! nvim_ghost#update_buffer(bufnr) abort " {{{1
  let l:timer = nvim_buf_get_var(a:bufnr,'nvim_ghost_timer')
  if l:timer
    call timer_stop(l:timer)
  endif
  let l:timer = timer_start(g:nvim_ghost_debounce, {->execute('call nvim_ghost#send_buffer('.a:bufnr.')')})
  call nvim_buf_set_var(a:bufnr,'nvim_ghost_timer',l:timer)
endfunction

function! nvim_ghost#send_buffer(bufnr) abort " {{{1
  call nvim_ghost#request_focus()
  let l:job = jobstart([g:nvim_ghost_binary_path, '--update-buffer-text', a:bufnr], s:joblog_arguments)
  call chansend(l:job, getbufline(a:bufnr,1,'$'))
  call chanclose(l:job)
endfunction

function! nvim_ghost#request_focus() abort  " {{{1
  call jobstart([g:nvim_ghost_binary_path,'--focus' ,$NVIM_LISTEN_ADDRESS])
endfunction

function! nvim_ghost#notify_buffer_deleted(bufnr) abort " {{{1
  call nvim_ghost#request_focus()
  let l:job = jobstart([g:nvim_ghost_binary_path, '--buffer-closed', a:bufnr], s:joblog_arguments)
endfunction

function! nvim_ghost#setup_buffer_autocmds(bufnr) abort " {{{1
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
endfunction

function! nvim_ghost#delete_buffer_autocmds(bufnr) abort  " {{{1
  exe 'augroup nvim_ghost_' . a:bufnr
  exe 'au! nvim_ghost_'.a:bufnr
  exe 'augroup END'
endfunction

function! nvim_ghost#joboutput_logger(data,type) abort  " {{{1
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
endfunction

function! nvim_ghost#_can_use_cursorhold() abort  " {{{1
  let s:can_use_cursorhold = v:true
  for bufnr in s:bufnr_list
    call nvim_ghost#delete_buffer_autocmds(bufnr)
    call nvim_ghost#setup_buffer_autocmds(bufnr)
  endfor
endfunction

function! nvim_ghost#_buffer_enter() abort  " {{{1
  let s:saved_updatetime = &updatetime
  let &updatetime = g:nvim_ghost_updatetime
endfunction

function! nvim_ghost#_buffer_leave() abort  " {{{1
  let &updatetime = s:saved_updatetime
endfunction

function! nvim_ghost#session_closed() abort " {{{1
  if has('win32')
    call systemlist(['cscript.exe', g:nvim_ghost_script_path.'\session_closed.vbs'])
  else
    call systemlist([g:nvim_ghost_script_path.'/session_closed.sh'])
  endif
endfunction
  "}}}

" vim: et ts=2 fdm=marker
