/* Enforce direct-hour discrepancies without changing draft saves. */
(function(root){
  var dayNames=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];

  function minutes(value){
    if(!/^\d{2}:\d{2}$/.test(String(value||'')))return NaN;
    var parts=String(value).split(':').map(Number);
    return parts[0]*60+parts[1];
  }

  function paidLeaveHours(row,start,finish){
    var data=row.dataset||{};
    var leaveStart=minutes(data.leaveStart);
    var leaveEnd=minutes(data.leaveEnd);
    var approved=Number(data.leaveHours||0);
    if(!Number.isFinite(leaveStart)||!Number.isFinite(leaveEnd)||leaveEnd<=leaveStart)return 0;
    var overlap=Math.max(0,Math.min(finish,leaveEnd)-Math.max(start,leaveStart));
    if(!overlap)return 0;
    var lunchStart=minutes(data.leaveLunchStart);
    var lunchEnd=minutes(data.leaveLunchEnd);
    var hasLunch=Number.isFinite(lunchStart)&&Number.isFinite(lunchEnd);
    var lunchOverlap=hasLunch?Math.max(0,Math.min(finish,lunchEnd)-Math.max(start,lunchStart)):0;
    var paidMinutes=Math.max(0,overlap-lunchOverlap);
    var leaveSpan=leaveEnd-leaveStart;
    if(!hasLunch&&Number.isFinite(approved)&&approved>0&&leaveSpan>0&&Math.abs(leaveSpan/60-approved)>0.001)return approved*overlap/leaveSpan;
    return paidMinutes/60;
  }

  function directRowError(row){
    if(!row)return '';
    var status=row.querySelector('.status').value;
    var method=row.querySelector('.mode').value;
    if(status!=='Work'||method!=='direct')return '';

    var raw=row.querySelector('.direct').value;
    if(raw===''||raw===null||raw===undefined)return 'Enter paid direct hours.';
    var hours=Number(raw);
    if(!Number.isFinite(hours)||hours<0||hours>24||Math.abs(hours*4-Math.round(hours*4))>0.000001){
      return 'Enter paid direct hours from 0 to 24 in 0.25-hour steps.';
    }
    if(hours===0)return '';

    var start=row.querySelector('.start').value;
    var finish=row.querySelector('.finish').value;
    if(!start||!finish)return 'Enter actual start and finish times for custom direct hours.';
    var startMinutes=minutes(start),finishMinutes=minutes(finish),span=(finishMinutes-startMinutes)/60;
    if(!Number.isFinite(span)||span<=0)return 'Finish time must be after start time.';
    var lunch=row.querySelector('.unpaid-lunch').value==='unpaid'?Math.min(hours,0.5):0;
    var leavePay=paidLeaveHours(row,startMinutes,finishMinutes);
    var expected=span-lunch-leavePay;
    if(Math.abs(expected-hours)>0.001){
      return (leavePay>0?'Start, finish, lunch and approved leave':'Start, finish and lunch')+' do not match '+hours.toFixed(2)+' paid hours. Enter actual start and finish times.';
    }
    return '';
  }

  function updateChecks(){
    document.querySelectorAll('#rows tr').forEach(function(row){
      var check=row.querySelector('.direct-check');
      if(!check)return;
      var active=row.querySelector('.status').value==='Work'&&row.querySelector('.mode').value==='direct'&&Number(row.querySelector('.direct').value)>0;
      var error=directRowError(row);
      check.hidden=!active;
      check.className='direct-check'+(error?' err':'');
      check.setAttribute('role',error?'alert':'status');
      check.textContent=error||(Number(row.dataset.leaveHours||0)>0?'Start, finish, lunch and approved leave match paid hours.':'Start, finish and lunch match paid hours.');
    });
  }

  var originalCalc=root.calc;
  if(typeof originalCalc==='function'){
    root.calc=function(){
      var result=originalCalc.apply(this,arguments);
      updateChecks();
      return result;
    };
  }

  var originalCollectSheet=root.collectSheet;
  if(typeof originalCollectSheet==='function'){
    root.collectSheet=function(draft){
      var rows=Array.prototype.slice.call(document.querySelectorAll('#rows tr'));
      if(!draft){
        var problems=[];
        rows.forEach(function(row,index){
          var error=directRowError(row);
          if(error)problems.push(dayNames[index]+': '+error);
        });
        if(problems.length){
          if(typeof root.calc==='function')root.calc();
          throw new Error(problems[0]);
        }
      }
      var data=originalCollectSheet.apply(this,arguments);
      data.days.forEach(function(day){
        if(day.status!=='Work'||Number(day.hours)<=0){
          day.start='';
          day.finish='';
        }
      });
      return data;
    };
  }

  root.directRowError=directRowError;
  if(typeof root.calc==='function'&&document.querySelector('#rows tr'))root.calc();
  var help=document.querySelector('.timesheet-help p');
  if(help&&help.textContent.indexOf('Custom direct hours')===-1){
    help.textContent+=' The sheet cannot be submitted while start, finish, lunch and paid direct hours differ.';
  }
})(window);
