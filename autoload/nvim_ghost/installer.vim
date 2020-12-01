function! nvim_ghost#installer#install() abort
  let l:binary_path = g:nvim_ghost_binary_path
  let l:installation_dir = fnamemodify(g:nvim_ghost_binary_path, ':h')
  if filereadable(l:binary_path)
    let l:downloaded_version = systemlist(shellescape(l:binary_path) . ' --version')[0]
    let l:needed_version = readfile(l:installation_dir . '/.binary_version')[0]
    if l:needed_version =~# l:downloaded_version
      echom '[nvim-ghost] already using latest version, skipping binary download'
      return 0
    endif
  endif

  function! s:report_result(exitcode) abort
    if a:exitcode == 0
      echom 'nvim-ghost installed sucessfully'
    else
      echohl ErrorMsg
      echom 'nvim-ghost installation failed ' . '(exit code: ' . a:exitcode . ')'
      echohl None
    endif
  endfunction

  if has('win32')
    let l:command = (executable('pwsh.exe') ? 'pwsh.exe' : 'powershell.exe')
    let l:command .= ' -Command ' . shellescape('Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force; & ' . shellescape(l:installation_dir . '/scripts/install_binary.ps1'))
    let l:term_height = 8
  else
    let l:command = fnameescape(l:installation_dir) . '/scripts/install_binary.sh'
    let l:term_height = 4
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
