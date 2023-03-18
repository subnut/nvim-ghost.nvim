if !has('nvim')
  finish
endif

function! nvim_ghost#init()
  if !g:nvim_ghost_use_script && (!filereadable(g:nvim_ghost_binary_path) ||
        \ readfile(g:nvim_ghost_installation_dir .. 'binary_version')[0]  !=
        \ readfile(g:nvim_ghost_binary_path .. ".version")[0]
        \)
    call nvim_ghost#installer#install(function("nvim_ghost#enable"))
  else
    call nvim_ghost#enable(1)
  endif
endfunction

function! s:start_server_or_request_focus()
  " If we start the server, we are already focused, so we don't need to
  " request_focus separately
  if ! nvim_ghost#helper#is_running()
    call nvim_ghost#helper#start_server()
  else
    call nvim_ghost#helper#request_focus()
  endif
endfunction

function! nvim_ghost#disable()
  call nvim_ghost#helper#session_closed()
  autocmd! nvim_ghost
  if !exists('g:_nvim_ghost_supports_focus')
    autocmd! _nvim_ghost_does_not_support_focus
  endif
endfunction

function! nvim_ghost#enable(defer = 0)
  if !a:defer
    call s:start_server_or_request_focus()
  endif

  augroup nvim_ghost
    autocmd!
    if a:defer
      autocmd UIEnter   * call s:start_server_or_request_focus()
    endif
    autocmd FocusGained * call nvim_ghost#helper#request_focus()
    autocmd VimLeavePre * call nvim_ghost#helper#session_closed()
  augroup END

  " :doau causes error if augroup not defined
  if !exists('#nvim_ghost_user_autocommands')
    augroup nvim_ghost_user_autocommands
      autocmd!
    augroup END
  endif

  " Compatibility for terminals that do not support focus
  " Uses CursorMoved to detect focus

  if !exists('g:_nvim_ghost_supports_focus')
    let g:_nvim_ghost_supports_focus = 0

    " vint: next-line -ProhibitAutocmdWithNoGroup
    autocmd FocusGained,FocusLost * ++once
          \  let g:_nvim_ghost_supports_focus = 1
          \| au! _nvim_ghost_does_not_support_focus

    augroup _nvim_ghost_does_not_support_focus
      au!
      autocmd CursorMoved,CursorMovedI * call s:focus_gained()
      autocmd CursorHold,CursorHoldI * let s:focused = v:false
    augroup END

    let s:focused = v:true
    fun! s:focus_gained()
      if !s:focused
        call nvim_ghost#helper#request_focus()
        let s:focused = v:true
      endif
    endfun
  endif
endfunction

" vim: et ts=2 sts=0 sw=0 fdm=marker
