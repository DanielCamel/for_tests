import java.util.*;
public class MyTimer {
	Date d=new Date();
	public void printTime(String text)
	{
		System.out.println(text+": "+(new Date().getTime()-d.getTime())+" ms");
	}
}
