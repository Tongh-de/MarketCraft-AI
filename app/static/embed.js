if(new URLSearchParams(window.location.search).get("embed")==="1"){
  document.body.classList.add("embed-mode");
  document.querySelectorAll('a[href^="/"]').forEach((link)=>{
    if(link.getAttribute("href")!=="/docs")link.setAttribute("target","_top");
  });
}
