if !has('nvim')
  finish
endif

if exists('g:loaded_nvim_ghost')
  finish
endif
let g:loaded_nvim_ghost = 1

if has('win32')
  let s:localhost = "127.0.0.1"
else
  let s:localhost = "localhost"
endif

if !exists('$GHOSTTEXT_SERVER_PORT')
  let $GHOSTTEXT_SERVER_PORT = 4001
endif

let s:saved_updatetime = &updatetime
let s:can_use_cursorhold = v:false
let s:joblog_arguments = {
      \'on_stdout':{id,data,type->nvim_ghost#joboutput_logger(data,type)},
      \'on_stderr':{id,data,type->nvim_ghost#joboutput_logger(data,type)},
      \}
let s:joblog_arguments_nokill = extend(copy(s:joblog_arguments), {
      \'detach': v:true,
      \'cwd': g:nvim_ghost_installation_dir,
      \})

function! s:send_GET_request(url) "{{{1
  let l:connection = sockconnect('tcp', s:localhost . ':' . $GHOSTTEXT_SERVER_PORT , {})
  " Each line of request data MUST end with a \r followed by a \n
  " NOTE: Use "" instead of '', otherwise vim shall interpret \r\n literally
  " instead of their actual intended meaning
  call chansend(l:connection, 'GET ' . a:url . ' HTTP/1.1' . "\r\n")
  " To _flush_ the channel, we send a newline
  " NOTE: again, we need to use "" instead of ''
  call chansend(l:connection, "\n")
  " We're done, close the channel and report
  call chanclose(l:connection)
  call nvim_ghost#joboutput_logger(['Sent ' . a:url], '')
endfunction

function! nvim_ghost#start_server() abort " {{{1
  if has('win32')
    call jobstart(['cscript.exe', g:nvim_ghost_script_path.'\start_server.vbs'])
  else
    call jobstart([g:nvim_ghost_binary_path, '--start-server'], s:joblog_arguments_nokill)
  endif
endfunction

function! nvim_ghost#kill_server() abort  " {{{1
  " call jobstart([g:nvim_ghost_binary_path, '--kill'], s:joblog_arguments)
  call s:send_GET_request('/exit')
endfunction

function! nvim_ghost#request_focus() abort  " {{{1
  " call jobstart([g:nvim_ghost_binary_path,'--focus'], s:joblog_arguments)
  call s:send_GET_request('/focus?focus=' . v:servername)
endfunction

function! nvim_ghost#session_closed() abort " {{{1
  " call jobstart([g:nvim_ghost_binary_path, '--session-closed'], s:joblog_arguments_nokill)
  call s:send_GET_request('/session-closed?session=' . v:servername)
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
endfunction "}}}1


" vim: et ts=2 fdm=marker
