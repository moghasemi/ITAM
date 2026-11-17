/* ITAM UI behavior — Metronic 9 shell + legacy workflow helpers. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    setupSidebar(); setupSidebarCollapse(); setupThemeToggle(); setupUserMenu();
    setupAlerts(); setupConfirm(); setupFormsets(); setupJalaliInputs();
    setupTabs(); setupPrintButtons(); setupSearchShortcuts();
  });

  function setupSidebar() {
    var sidebar=document.getElementById("sidebar"), backdrop=document.getElementById("sidebar_backdrop");
    var toggles=document.querySelectorAll("[data-toggle='sidebar']");
    if(!sidebar)return;
    function closeSidebar(){
      sidebar.classList.remove("open");document.body.classList.remove("itam-sidebar-open");
      if(backdrop)backdrop.hidden=true;
      toggles.forEach(function(b){b.setAttribute("aria-expanded","false");});
    }
    function openSidebar(){
      sidebar.classList.add("open");document.body.classList.add("itam-sidebar-open");
      if(backdrop)backdrop.hidden=false;
      toggles.forEach(function(b){b.setAttribute("aria-expanded","true");});
    }
    toggles.forEach(function(button){button.addEventListener("click",function(){
      sidebar.classList.contains("open")?closeSidebar():openSidebar();
    });});
    if(backdrop)backdrop.addEventListener("click",closeSidebar);
    sidebar.querySelectorAll("a").forEach(function(link){link.addEventListener("click",function(){
      if(window.matchMedia("(max-width: 1023px)").matches)closeSidebar();
    });});
    document.addEventListener("keydown",function(event){if(event.key==="Escape")closeSidebar();});
    window.addEventListener("resize",function(){if(window.matchMedia("(min-width: 1024px)").matches)closeSidebar();});
  }

  function setupSidebarCollapse() {
    var button=document.querySelector("[data-sidebar-collapse]");if(!button)return;
    try{if(localStorage.getItem("itam-sidebar-collapsed")==="1"&&window.matchMedia("(min-width: 1024px)").matches)
      document.body.classList.add("itam-sidebar-collapsed");}catch(error){}
    button.addEventListener("click",function(){
      document.body.classList.toggle("itam-sidebar-collapsed");
      try{localStorage.setItem("itam-sidebar-collapsed",document.body.classList.contains("itam-sidebar-collapsed")?"1":"0");}catch(error){}
    });
  }

  function setupThemeToggle() {
    var button=document.querySelector("[data-theme-toggle]");if(!button)return;
    function apply(mode){
      var dark=mode==="dark";
      document.documentElement.classList.toggle("dark",dark);
      document.documentElement.setAttribute("data-kt-theme-mode",dark?"dark":"light");
      button.setAttribute("aria-pressed",dark?"true":"false");
      button.setAttribute("title",dark?"فعال‌کردن پوسته روشن":"فعال‌کردن پوسته تاریک");
      try{localStorage.setItem("kt-theme",dark?"dark":"light");}catch(error){}
    }
    button.addEventListener("click",function(){apply(document.documentElement.classList.contains("dark")?"light":"dark");});
  }

  function setupUserMenu() {
    var chip=document.querySelector(".user-chip"),menu=document.querySelector(".user-menu");
    if(!chip||!menu)return;
    chip.style.cursor="pointer";
    chip.addEventListener("click",function(event){event.stopPropagation();menu.classList.toggle("open");});
    document.addEventListener("click",function(){menu.classList.remove("open");});
  }

  function setupAlerts() {
    document.querySelectorAll("[data-dismiss='alert']").forEach(function(button){
      button.addEventListener("click",function(){var alert=button.closest(".alert");if(alert)alert.remove();});
    });
    window.setTimeout(function(){
      document.querySelectorAll(".messages .alert-success").forEach(function(alert){
        alert.style.transition="opacity .35s";alert.style.opacity="0";
        window.setTimeout(function(){alert.remove();},380);
      });
    },6500);
  }

  function setupConfirm() {
    document.querySelectorAll("form[data-confirm]").forEach(function(form){
      form.addEventListener("submit",function(event){
        if(!window.confirm(form.getAttribute("data-confirm")))event.preventDefault();
      });
    });
  }

  function setupFormsets() {
    document.querySelectorAll("[data-formset]").forEach(function(container){
      var prefix=container.getAttribute("data-prefix")||"form";
      var totalInput=container.querySelector("input[name='"+prefix+"-TOTAL_FORMS']");
      var rowsContainer=container.querySelector(".formset-rows");
      var template=container.querySelector("template[data-formset-empty]");
      var addButton=container.querySelector("[data-formset-add]");
      if(!totalInput||!rowsContainer||!template||!addButton)return;
      addButton.addEventListener("click",function(){
        var index=parseInt(totalInput.value,10)||0,html=template.innerHTML.split("__prefix__").join(index);
        var wrapper=document.createElement("div");wrapper.innerHTML=html.trim();
        var row=wrapper.firstElementChild;
        if(row){rowsContainer.appendChild(row);totalInput.value=index+1;}
      });
      rowsContainer.addEventListener("click",function(event){
        var removeButton=event.target.closest("[data-formset-remove]");if(!removeButton)return;
        var row=removeButton.closest("[data-formset-row]");if(row)row.remove();
      });
    });
  }

  function setupJalaliInputs() {
    document.querySelectorAll("input.jalali-date,input.jalali-datetime").forEach(function(input){
      input.setAttribute("autocomplete","off");
      input.addEventListener("input",function(){
        var withTime=input.classList.contains("jalali-datetime");
        var digits=toLatinDigits(input.value).replace(/[^\d]/g,""),out="";
        if(digits.length>0)out+=digits.substring(0,4);
        if(digits.length>4)out+="/"+digits.substring(4,6);
        if(digits.length>6)out+="/"+digits.substring(6,8);
        if(withTime&&digits.length>8){out+=" "+digits.substring(8,10);if(digits.length>10)out+=":"+digits.substring(10,12);}
        input.value=out;
      });
    });
  }

  function toLatinDigits(text) {
    var persian="۰۱۲۳۴۵۶۷۸۹",arabic="٠١٢٣٤٥٦٧٨٩";
    return String(text||"").replace(/[۰-۹٠-٩]/g,function(char){
      var index=persian.indexOf(char);if(index===-1)index=arabic.indexOf(char);
      return index===-1?char:String(index);
    });
  }

  function setupTabs() {
    document.querySelectorAll("[data-tabs]").forEach(function(group){
      var buttons=group.querySelectorAll(".tab");
      buttons.forEach(function(button){button.addEventListener("click",function(){
        var target=button.getAttribute("data-tab-target"),scope=group.closest("[data-tabs-scope]");
        buttons.forEach(function(item){item.classList.remove("active");});button.classList.add("active");
        document.querySelectorAll("[data-tab-panel]").forEach(function(panel){
          if(panel.closest("[data-tabs-scope]")!==scope)return;
          panel.classList.toggle("active",panel.getAttribute("data-tab-panel")===target);
        });
      });});
      try{var focus=new URLSearchParams(window.location.search).get("focus");
        if(focus){var target=group.querySelector(".tab[data-tab-target='"+focus+"']");if(target)target.click();}
      }catch(error){}
    });
  }

  function setupPrintButtons() {
    document.querySelectorAll("[data-print]").forEach(function(button){
      button.addEventListener("click",function(event){event.preventDefault();window.print();});
    });
  }

  function setupSearchShortcuts() {
    var search=document.querySelector(".itam-global-search input");if(!search)return;
    document.addEventListener("keydown",function(event){
      var tag=event.target&&event.target.tagName?event.target.tagName.toLowerCase():"";
      var editing=tag==="input"||tag==="textarea"||(event.target&&event.target.isContentEditable);
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){event.preventDefault();search.focus();}
      else if(event.key==="/"&&!editing&&!event.ctrlKey&&!event.metaKey&&!event.altKey){event.preventDefault();search.focus();}
    });
  }
})();
