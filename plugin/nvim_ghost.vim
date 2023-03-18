if !has('nvim')
  finish
endif

if get(g:,'nvim_ghost_disabled', 0)
  finish
endif

" Config
let g:nvim_ghost_autostart        = get(g:,'nvim_ghost_autostart', 1)
let g:nvim_ghost_use_script       = get(g:,'nvim_ghost_use_script', 0)
let g:nvim_ghost_super_quiet      = get(g:,'nvim_ghost_super_quiet', 0)
let g:nvim_ghost_logging_enabled  = get(g:,'nvim_ghost_logging_enabled', 0)
let g:nvim_ghost_server_port      = get(g:,'nvim_ghost_server_port', get(environ(),'GHOSTTEXT_SERVER_PORT', 4001))

" Directories (must end with g:nvim_ghost_pathsep)
let g:nvim_ghost_pathsep            = has('win32') ? '\' : '/'
let g:nvim_ghost_installation_dir   = expand('<sfile>:h:h')
let g:nvim_ghost_installation_dir ..= g:nvim_ghost_pathsep
let g:nvim_ghost_scripts_dir        = g:nvim_ghost_installation_dir . 'scripts'
let g:nvim_ghost_scripts_dir      ..= g:nvim_ghost_pathsep

" Files
let g:nvim_ghost_script_path = g:nvim_ghost_installation_dir .. 'binary.py'
let g:nvim_ghost_binary_path = g:nvim_ghost_installation_dir .. 'nvim-ghost-binary' .. (has('win32') ? '.exe' : '')

" Setup environment
let $NVIM_LISTEN_ADDRESS        = v:servername
let $NVIM_GHOST_SUPER_QUIET     = g:nvim_ghost_super_quiet
let $NVIM_GHOST_LOGGING_ENABLED = g:nvim_ghost_logging_enabled
let $GHOSTTEXT_SERVER_PORT      = g:nvim_ghost_server_port

" Abort if script_mode is enabled but infeasible
if g:nvim_ghost_use_script
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

" If autostart is disabled, add GhostTextStart command
if !g:nvim_ghost_autostart
  command! GhostTextStart
        \  let g:nvim_ghost_disabled = 0
        \| call nvim_ghost#init()
        \| doau <nomodeline> nvim_ghost UIEnter
        \| delcommand GhostTextEnable
  finish
endif

" Initialize plugin
call nvim_ghost#init()

" vim: et ts=2 sts=0 sw=0 nowrap
