if !has('nvim')
  finish
endif

let g:nvim_ghost_installation_dir = expand('<sfile>:h:h')
let g:nvim_ghost_binary_path  =  g:nvim_ghost_installation_dir . (has('win32') ? '\nvim-ghost-binary.exe' :  '/nvim-ghost-binary')
let g:nvim_ghost_script_path  =  g:nvim_ghost_installation_dir . (has('win32') ? '\scripts' :  '/scripts')
let g:nvim_ghost_logging_enabled = get(g:,'nvim_ghost_logging_enabled', 0)
let g:nvim_ghost_super_quiet = get(g:,'nvim_ghost_super_quiet', 0)

if get(g:,'nvim_ghost_use_script', 0)
  if has('win32')
    echohl WarningMsg
    echom 'Sorry, g:nvim_ghost_use_script is currently not available on
          \ Windows. Please remove it from your init.vim to use nvim-ghost.'
    echohl None
    finish
  endif
  if !exists('g:nvim_ghost_python_executable')
    echohl WarningMsg
    echom 'Please set g:nvim_ghost_python_executable
          \ to the location of the python executable'
    echohl None
    finish
  endif
endif

if get(g:,'nvim_ghost_disabled',0)
  let s:filename = expand('<sfile>:p')
  command! GhostTextEnable
        \  let g:nvim_ghost_disabled = 0
        \| execute('source '.s:filename)
        \| doau <nomodeline> nvim_ghost UIEnter
        \| delcommand GhostTextEnable
  finish
endif

if g:nvim_ghost_logging_enabled
  let $NVIM_GHOST_LOGGING_ENABLED = 1
endif

if g:nvim_ghost_super_quiet
  let $NVIM_GHOST_SUPER_QUIET = 1
endif

if $NVIM_LISTEN_ADDRESS != v:servername
  let $NVIM_LISTEN_ADDRESS = v:servername
endif

if !filereadable(g:nvim_ghost_binary_path)
  echohl WarningMsg
  echom '[nvim-ghost] Binary not installed. Please run :call nvim_ghost#installer#install() and restart neovim.'
  echohl None
  finish
endif

augroup nvim_ghost
  autocmd!
  autocmd UIEnter     * call nvim_ghost#start_server() | call nvim_ghost#request_focus()
  autocmd FocusGained * call nvim_ghost#request_focus()
  autocmd VimLeavePre * call nvim_ghost#session_closed()
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
      call nvim_ghost#request_focus()
      let s:focused = v:true
    endif
  endfun
endif

" vim: et ts=2 sts=0 sw=0 nowrap
