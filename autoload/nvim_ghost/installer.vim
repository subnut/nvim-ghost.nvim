function! s:report_result(exitcode) abort
  if a:exitcode == 0
    echom '[nvim-ghost] Installed sucessfully'
    call nvim_ghost#start_server()
  else
    echohl ErrorMsg
    echom '[nvim-ghost] Installation failed ' . '(exit code: ' . a:exitcode . ')'
    echohl None
  endif
endfunction


function! nvim_ghost#installer#install() abort
  let l:installation_dir = fnamemodify(g:nvim_ghost_binary_path, ':h')

  if filereadable(g:nvim_ghost_binary_path)
    let l:downloaded_version = systemlist(shellescape(g:nvim_ghost_binary_path) . ' --version')[0]
    let l:needed_version = readfile(l:installation_dir . '/binary_version')[0]
    if l:needed_version =~# trim(l:downloaded_version)
      echom '[nvim-ghost] Binary up-to-date'
      return 0
    endif
  endif

  if has('win32')
    let l:term_height = 8
    let l:command = (executable('pwsh.exe') ? 'pwsh.exe' : 'powershell.exe')
          \. ' -Command '
          \. shellescape('Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force; & '
          \. shellescape(g:nvim_ghost_scripts_dir . 'install_binary.ps1'))
  else
    let l:term_height = 4
    let l:command = g:nvim_ghost_scripts_dir . 'install_binary.sh'
  endif


  if has('nvim') && exists(':terminal') == 2
    " neovim with :terminal support
    " vint: next-line -ProhibitUnusedVariable
    function! s:callback(...) abort
      if a:2 == 0 " exitcode
        " no errors to report, so delete buffer
        call execute(s:terminal_bufnr . 'bd!')
        unlet s:terminal_bufnr
      endif
      call s:report_result(a:2)
    endfun
    let l:winid = win_getid()
    exe (&splitbelow ? 'botright' : 'topleft') . l:term_height . 'sp'
    enew
    call termopen(l:command, {'on_exit': function('s:callback')})
    set nobuflisted
    let s:terminal_bufnr = bufnr()
    call win_gotoid(l:winid)

  elseif has('nvim')
    " Neovim does not show any stdout output if called with :call execute(),
    " therefore to show the download progress bar, we need to call execute() by
    " itself.
    execute('!' . l:command)
    call s:report_result(v:shell_error)

  elseif has('terminal')
    " vim with +terminal
    " vint: next-line -ProhibitUnusedVariable
    function! s:callback(channel) abort
      let l:exitcode = job_info(ch_getjob(a:channel)).exitval
      if l:exitcode == 0
      " no errors to report, so delete buffer
        execute(s:terminal_bufnr . 'bd!')
        unlet s:terminal_bufnr
      endif
      call s:report_result(l:exitcode)
    endfun
    let l:winid = win_getid()
    exe (&splitbelow ? 'botright' : 'topleft') . " call term_start(l:command, {'term_rows': " . l:term_height . ", 'close_cb': function('s:callback')})"
    set nobuflisted
    let s:terminal_bufnr = bufnr()
    call win_gotoid(l:winid)

  else
    " vim without terminal support
    call execute('!' . l:command)
    call s:report_result(v:shell_error)
  endif
endfunction
