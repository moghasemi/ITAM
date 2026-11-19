/* ITAM UI behavior — Metronic 9 shell + legacy workflow helpers. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    setupSidebar(); setupSidebarCollapse(); setupThemeToggle();
    setupAlerts(); setupConfirm(); setupFormsets(); setupJalaliInputs();
    setupTabs(); setupPrintButtons(); setupSearchShortcuts();
  });

  function setupSidebar() {
    var sidebar=document.getElementById("sidebar"), backdrop=document.getElementById("sidebar_backdrop");
    var toggles=document.querySelectorAll("[data-toggle='sidebar']");
    if(!sidebar)return;

    var mobileQuery=window.matchMedia("(max-width: 1023px)");
    var lastToggle=null;

    function setExpanded(expanded){
      toggles.forEach(function(button){button.setAttribute("aria-expanded",expanded?"true":"false");});
    }

    function setUnavailable(unavailable){
      sidebar.setAttribute("aria-hidden",unavailable?"true":"false");
      if(unavailable)sidebar.setAttribute("inert","");
      else sidebar.removeAttribute("inert");
    }

    function getFocusableItems(){
      return Array.prototype.slice.call(sidebar.querySelectorAll(
        "a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex='-1'])"
      )).filter(function(element){
        return element.getClientRects().length>0 && element.getAttribute("aria-hidden")!=="true";
      });
    }

    function closeSidebar(restoreFocus){
      var wasOpen=sidebar.classList.contains("open");
      if(restoreFocus && wasOpen && lastToggle && lastToggle.getClientRects().length>0){
        lastToggle.focus();
      }
      sidebar.classList.remove("open");
      document.body.classList.remove("itam-sidebar-open");
      if(backdrop)backdrop.hidden=true;
      setExpanded(false);
      setUnavailable(mobileQuery.matches);
    }

    function openSidebar(){
      if(!mobileQuery.matches)return;
      lastToggle=document.activeElement;
      sidebar.classList.add("open");
      document.body.classList.add("itam-sidebar-open");
      if(backdrop)backdrop.hidden=false;
      setUnavailable(false);
      setExpanded(true);
      var items=getFocusableItems();
      var firstMenuLink=sidebar.querySelector(".kt-menu-link");
      if(firstMenuLink && firstMenuLink.getClientRects().length>0)firstMenuLink.focus();
      else if(items.length)items[0].focus();
      else sidebar.focus();
    }

    toggles.forEach(function(button){
      button.addEventListener("click",function(){
        if(sidebar.classList.contains("open"))closeSidebar(true);
        else openSidebar();
      });
    });

    if(backdrop)backdrop.addEventListener("click",function(){closeSidebar(true);});
    sidebar.querySelectorAll("a[href]").forEach(function(link){
      link.addEventListener("click",function(){
        if(mobileQuery.matches)closeSidebar(true);
      });
    });

    document.addEventListener("keydown",function(event){
      if(!mobileQuery.matches || !sidebar.classList.contains("open"))return;
      if(event.key==="Escape"){
        event.preventDefault();
        closeSidebar(true);
        return;
      }
      if(event.key!=="Tab")return;
      var items=getFocusableItems();
      if(!items.length){
        event.preventDefault();
        sidebar.focus();
        return;
      }
      var first=items[0],last=items[items.length-1];
      if(event.shiftKey && (document.activeElement===first || !sidebar.contains(document.activeElement))){
        event.preventDefault();
        last.focus();
      }else if(!event.shiftKey && (document.activeElement===last || !sidebar.contains(document.activeElement))){
        event.preventDefault();
        first.focus();
      }
    });

    window.addEventListener("resize",function(){
      if(!mobileQuery.matches)closeSidebar(false);
      else if(!sidebar.classList.contains("open"))setUnavailable(true);
    });

    if(mobileQuery.matches)closeSidebar(false);
    else setUnavailable(false);
  }

  function setupSidebarCollapse() {
    var button=document.querySelector("[data-sidebar-collapse]");
    var sidebar=document.getElementById("sidebar");
    if(!button)return;
    function syncState(){
      var collapsed=document.body.classList.contains("itam-sidebar-collapsed");
      button.setAttribute("aria-pressed",collapsed?"true":"false");
      button.setAttribute("aria-expanded",collapsed?"false":"true");
      button.setAttribute("aria-label",collapsed?"بازکردن منوی کناری":"جمع‌کردن منوی کناری");
      button.setAttribute("title",collapsed?"بازکردن منوی کناری":"جمع‌کردن منوی کناری");
      if(sidebar)sidebar.querySelectorAll(".kt-menu-link").forEach(function(link){
        var label=link.querySelector(".kt-menu-title");
        if(collapsed&&label){
          var accessibleLabel=label.textContent.trim();
          link.setAttribute("title",accessibleLabel);
          link.setAttribute("aria-label",accessibleLabel);
        }else{
          link.removeAttribute("title");
          link.removeAttribute("aria-label");
        }
      });
    }
    try{if(localStorage.getItem("itam-sidebar-collapsed")==="1"&&window.matchMedia("(min-width: 1024px)").matches)
      document.body.classList.add("itam-sidebar-collapsed");}catch(error){}
    syncState();
    button.addEventListener("click",function(){
      document.body.classList.toggle("itam-sidebar-collapsed");
      try{localStorage.setItem("itam-sidebar-collapsed",document.body.classList.contains("itam-sidebar-collapsed")?"1":"0");}catch(error){}
      syncState();
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
      var buttons=Array.prototype.slice.call(group.querySelectorAll("[role='tab']"));
      var scope=group.closest("[data-tabs-scope]")||document;
      var panels=Array.prototype.slice.call(scope.querySelectorAll("[role='tabpanel']"));

      function activate(button, moveFocus){
        if(!button)return;
        var panelId=button.getAttribute("aria-controls");
        buttons.forEach(function(item){
          var selected=item===button;
          item.classList.toggle("active",selected);
          item.setAttribute("aria-selected",selected?"true":"false");
          item.setAttribute("tabindex",selected?"0":"-1");
        });
        panels.forEach(function(panel){
          var selected=panel.id===panelId;
          panel.classList.toggle("active",selected);
          panel.hidden=!selected;
        });
        if(moveFocus)button.focus();
      }

      buttons.forEach(function(button,index){
        button.addEventListener("click",function(){activate(button,false);});
        button.addEventListener("keydown",function(event){
          var nextIndex=index;
          if(event.key==="ArrowRight")nextIndex=(index+1)%buttons.length;
          else if(event.key==="ArrowLeft")nextIndex=(index-1+buttons.length)%buttons.length;
          else if(event.key==="Home")nextIndex=0;
          else if(event.key==="End")nextIndex=buttons.length-1;
          else return;
          event.preventDefault();
          activate(buttons[nextIndex],true);
        });
      });

      var selected=buttons.find(function(button){return button.getAttribute("aria-selected")==="true";})
        ||buttons.find(function(button){return button.classList.contains("active");})
        ||buttons[0];
      activate(selected,false);

      try{
        var focus=new URLSearchParams(window.location.search).get("focus");
        if(focus){
          var target=buttons.find(function(button){return button.getAttribute("data-tab-target")===focus;});
          if(target)activate(target,false);
        }
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
