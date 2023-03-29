if !has('nvim')
  finish
endif

function! nvim_ghost#helpers#buf_del(bufnum) abort
  if !g:nvim_ghost_keep_buffers
    exe "bdelete " .. a:bufnum
    return
  endif
  exe a:bufnum .. "bufdo setl buftype="
endfunction
