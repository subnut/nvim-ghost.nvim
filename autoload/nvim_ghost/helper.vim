if !has('nvim')
  finish
endif

if has('win32')
  let s:localhost = '127.0.0.1'
else
  let s:localhost = 'localhost'
endif

let s:saved_updatetime = &updatetime
let s:can_use_cursorhold = v:false
let s:joblog_arguments = !g:nvim_ghost_logging_enabled ? {} : {
      \'on_stdout':{id,data,type->nvim_ghost#helper#joboutput_logger(data,type)},
      \'on_stderr':{id,data,type->nvim_ghost#helper#joboutput_logger(data,type)},
      \}
let s:joblog_arguments_nokill = extend(copy(s:joblog_arguments), {
      \'detach': v:true,
      \'cwd': g:nvim_ghost_installation_dir,
      \})

function! nvim_ghost#helper#is_running() abort  " {{{1
  " See s:send_GET_request for explanation on how this works
  let v:errmsg = ''
  let l:url = s:localhost .. ':' .. $GHOSTTEXT_SERVER_PORT
  let l:opts = {
        \'on_data': {id,data,name->chanclose(id)},
        \'data_buffered': v:true,
        \}
  silent! let l:connection = sockconnect('tcp', l:url, l:opts)
  if v:errmsg !=# '' || l:connection == 0
    return v:false
  endif
  return v:true
endfunction

function! s:send_GET_request(url) abort "{{{1
  let l:url = s:localhost . ':' . $GHOSTTEXT_SERVER_PORT

  " We need to close the connection, but if we close the connection
  " immediately after sending the data, then python's server shall complain
  " "Broken Pipe", and shall not process our request.  So, we shall only close
  " the channel when all of the data has been received.

  " To ensure that we receive all data, we use the 'data_buffered' option.
  " And to ensure that the channel is automatically closed when we receive the
  " server's response, we use the 'on_data' option.
  let l:opts = {
        \'on_data': {id,data,name->chanclose(id)},
        \'data_buffered': v:true,
        \}

  " We use silent! to stop error messages from popping up on the screen
  " unnecessarily.
  " We can't use try-catch with silent! because silent! also suppresses the
  " exception.  The only thing that silent! doesn't suppress is v:errmsg.
  let v:errmsg = ''
  silent! let l:connection = sockconnect('tcp', l:url, l:opts)
  if v:errmsg !=# '' || l:connection == 0
    if g:nvim_ghost_super_quiet != 1
      echohl WarningMsg
      echom '[nvim-ghost] Could not connect to ' . l:url
      echohl None
    endif
    return 1
  endif

  " Each line of request data MUST end with a \r followed by a \n, and the end
  " of headers is indicated with a \r\n on a line by itself.
  " NOTE: Use "" instead of '', otherwise vim shall interpret \r\n literally
  " instead of their actual intended meaning (Carriage Return and Newline)

  " Headers
  call chansend(l:connection, 'GET ' . a:url . ' HTTP/1.1' . "\r\n")
  " End of headers
  call chansend(l:connection, "\r\n")

  " We're done, log what we sent
  call nvim_ghost#helper#joboutput_logger(['Sent ' . a:url], '')
endfunction

function! nvim_ghost#helper#start_server() abort " {{{1
  if has('win32')
    call jobstart(['cscript.exe',
          \g:nvim_ghost_scripts_dir . 'start_server.vbs'])
  else
    if g:nvim_ghost_use_script
      call jobstart(
            \[g:nvim_ghost_python_executable, g:nvim_ghost_script_path],
            \s:joblog_arguments_nokill
            \)
    else
      call jobstart([g:nvim_ghost_binary_path], s:joblog_arguments_nokill)
    endif
  endif
endfunction

function! nvim_ghost#helper#kill_server() abort  " {{{1
  call s:send_GET_request('/exit')
endfunction

function! nvim_ghost#helper#request_focus() abort  " {{{1
  call s:send_GET_request('/focus?focus=' . v:servername)
endfunction

function! nvim_ghost#helper#session_closed() abort " {{{1
  call s:send_GET_request('/session-closed?session=' . v:servername)
endfunction
function! nvim_ghost#helper#joboutput_logger(data,type) abort  " {{{1
  if !g:nvim_ghost_logging_enabled || g:nvim_ghost_super_quiet
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
"}}}1

" vim: et ts=2 sts=0 sw=0 fdm=marker
