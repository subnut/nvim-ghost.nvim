if get(s:, 'loaded', 0)
    finish
endif
let s:loaded = 1
let s:project_parent_folder_path = fnamemodify(resolve(expand('<sfile>:p')), ':h:h')

fun! s:start_server()
    let s:server_job = jobstart('python ' . s:project_parent_folder_path . 'server.py')     " Find a way to get the directory and execute the file
endfun

fun! s:trigger_start()
    " let s:saved_updatetime = &updatetime
    " set updatetime=800      " Used in live-update by CursorHold and CursorHoldI autocommands
    "
    " Better implement the above using "setlocal updatetime=800"
    " i.e. local to buffer
    "
    " "ftplugin?"
    " maybe set "ft=ghost" on first buffer-making?
    " from the server.py? using API?
    " and create a ftplugin with thsi command?
    " Yay!
    "
    " EDIT: That will not work
    " Use somethin like this-
autocmd BufEnter * set updatetime=4000
autocmd BufEnter *.ghost set updatetime=100

    call s:start_server()
    augroup vim_ghost
        au!
        au CursorHold,CursorHoldI * call s:update_buffer_to_broswer()
    augroup end
endfun

fun! s:trigger_end()
    execute('set updatetime=' . s:saved_updatetime)
endfun
